import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from sqlmodel import Session, select, func

from db.database import get_session
from db import chroma_client
from collections import defaultdict

from models.message import (
    Message,
    MessageCreate,
    MessageResponse,
    ConversationSummary,
    ContextRequest,
    ContextResponse,
    SearchRequest,
    SearchResult,
    TimelineGroup,
    RelatedConversation,
    ProjectGroup,
    GraphNode,
    GraphEdge,
    GraphData,
)
from services.search import keyword_search
from services import summarizer, context

logger = logging.getLogger(__name__)
router = APIRouter()


def _embed_and_index(message: Message):
    """后台任务：生成 embedding 并存入 ChromaDB。"""
    try:
        chroma_client.add_message(
            msg_id=message.id,
            content=message.content,
            metadata={
                "platform": message.platform,
                "conversation_id": message.conversation_id,
                "role": message.role,
            },
        )
    except Exception as e:
        logger.error(f"Embedding 失败: {e}")


def _auto_summarize(session_factory, conversation_id: str):
    """后台任务：自动为对话生成摘要。"""
    try:
        with next(session_factory()) as session:
            messages = session.exec(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.timestamp.asc())
            ).all()

            if len(messages) < 2:
                return

            msg_dicts = [{"role": m.role, "content": m.content} for m in messages]
            result = summarizer.generate_summary(msg_dicts)

            # 回写到该对话的所有消息
            for msg in messages:
                if not msg.title:
                    msg.title = result["title"]
                if not msg.tags:
                    msg.tags = result["tags"]
                if not msg.summary:
                    msg.summary = result["summary"]

            session.commit()
            logger.info(f"对话摘要已生成: {conversation_id}")
    except Exception as e:
        logger.error(f"摘要生成失败: {e}")


@router.post("/messages", response_model=MessageResponse)
def create_message(
    msg: MessageCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """接收浏览器插件上传的消息。"""
    message = Message(
        id=uuid.uuid4().hex,
        platform=msg.platform,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content=msg.content,
        timestamp=msg.timestamp or datetime.now(timezone.utc),
    )
    session.add(message)
    session.commit()
    session.refresh(message)

    # 后台异步：embedding 向量化
    background_tasks.add_task(_embed_and_index, message)
    # 后台异步：自动摘要（每个对话只做一次）
    background_tasks.add_task(
        _auto_summarize, get_session, message.conversation_id
    )

    return message


@router.get("/timeline", response_model=list[TimelineGroup])
def get_timeline(
    platform: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    session: Session = Depends(get_session),
):
    """获取 Timeline，按对话聚合，按日期分组。"""
    # 获取所有消息，按时间倒序
    query = select(Message)
    if platform:
        query = query.where(Message.platform == platform)
    query = query.order_by(Message.timestamp.desc())

    all_msgs = session.exec(query).all()

    # 按 conversation_id 聚合
    conv_map: dict[str, dict] = {}
    for msg in all_msgs:
        cid = msg.conversation_id
        if cid not in conv_map:
            conv_map[cid] = {
                "conversation_id": cid,
                "platform": msg.platform,
                "title": msg.title,
                "preview": "",
                "tags": msg.tags,
                "summary": msg.summary,
                "message_count": 0,
                "latest_timestamp": msg.timestamp,
                "first_user_content": None,
            }
        conv = conv_map[cid]
        conv["message_count"] += 1
        if msg.timestamp > conv["latest_timestamp"]:
            conv["latest_timestamp"] = msg.timestamp
        # 取最新的 title/tags/summary
        if msg.title and not conv["title"]:
            conv["title"] = msg.title
        if msg.tags and not conv["tags"]:
            conv["tags"] = msg.tags
        if msg.summary and not conv["summary"]:
            conv["summary"] = msg.summary
        # 取第一条用户消息作为预览
        if msg.role == "user":
            if conv["first_user_content"] is None or msg.timestamp < conv_map[cid].get("_first_user_ts", datetime.max):
                conv["first_user_content"] = msg.content
                conv["_first_user_ts"] = msg.timestamp

    # 生成 ConversationSummary 列表，按最新时间排序
    summaries = []
    for conv in conv_map.values():
        preview = conv["first_user_content"] or ""
        if len(preview) > 100:
            preview = preview[:100] + "..."
        summaries.append({
            "conversation": ConversationSummary(
                conversation_id=conv["conversation_id"],
                platform=conv["platform"],
                title=conv["title"],
                preview=preview,
                tags=conv["tags"],
                summary=conv["summary"],
                message_count=conv["message_count"],
                latest_timestamp=conv["latest_timestamp"],
            ),
            "latest_timestamp": conv["latest_timestamp"],
        })

    summaries.sort(key=lambda x: x["latest_timestamp"], reverse=True)
    summaries = summaries[offset:offset + limit]

    # 按日期分组
    groups: dict[str, list[ConversationSummary]] = {}
    for item in summaries:
        conv = item["conversation"]
        date_key = item["latest_timestamp"].strftime("%Y-%m-%d")
        if date_key not in groups:
            groups[date_key] = []
        groups[date_key].append(conv)

    return [
        TimelineGroup(date=date, conversations=convs)
        for date, convs in groups.items()
    ]


@router.get("/conversations/{conversation_id}", response_model=list[MessageResponse])
def get_conversation(conversation_id: str, session: Session = Depends(get_session)):
    """获取单个对话的完整消息列表。"""
    messages = session.exec(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp.asc())
    ).all()
    return [MessageResponse.model_validate(m) for m in messages]


@router.post("/search", response_model=list[SearchResult])
def search_messages(req: SearchRequest, session: Session = Depends(get_session)):
    """语义搜索：优先使用 ChromaDB 向量搜索，回退到关键词匹配。"""
    # 优先使用向量搜索
    vector_results = chroma_client.search_similar(req.query, top_k=20)

    if vector_results:
        results = []
        for item in vector_results:
            msg = session.get(Message, item["id"])
            if msg:
                results.append(
                    SearchResult(
                        message=MessageResponse.model_validate(msg),
                        score=item["score"],
                    )
                )
        if results:
            return results

    # 回退：关键词搜索
    fallback = keyword_search(session, req.query)
    return [
        SearchResult(message=MessageResponse.model_validate(msg), score=0.3)
        for msg in fallback
    ]


@router.post("/context", response_model=ContextResponse)
def get_context(req: ContextRequest, session: Session = Depends(get_session)):
    """生成上下文注入文本：输入当前讨论主题，返回可复制到 AI 平台的历史上下文。"""
    # 向量检索相关消息
    vector_results = chroma_client.search_similar(req.query, top_k=30)

    related_messages = []
    related_convs = []

    for item in vector_results:
        msg = session.get(Message, item["id"])
        if msg:
            related_messages.append(msg)

    # 收集相关对话摘要
    seen_convs = set()
    for msg in related_messages:
        if msg.conversation_id in seen_convs:
            continue
        seen_convs.add(msg.conversation_id)
        related_convs.append({
            "conversation_id": msg.conversation_id,
            "platform": msg.platform,
            "title": msg.title or msg.content[:60],
            "score": 1.0,
            "message_count": 0,
            "latest_timestamp": msg.timestamp,
        })

    # 生成上下文
    context_text, key_points = context.build_context(
        req.query, related_messages, related_convs
    )

    # 构建关联对话列表
    related_list = []
    for conv_data in related_convs[:5]:
        conv_msgs = session.exec(
            select(Message)
            .where(Message.conversation_id == conv_data["conversation_id"])
            .order_by(Message.timestamp.desc())
        ).all()
        msg_count = len(conv_msgs)
        latest = conv_msgs[0].timestamp if conv_msgs else conv_data["latest_timestamp"]
        related_list.append(RelatedConversation(
            conversation_id=conv_data["conversation_id"],
            title=conv_data["title"],
            platform=conv_data["platform"],
            score=conv_data["score"],
            message_count=msg_count,
            latest_timestamp=latest,
        ))

    return ContextResponse(
        query=req.query,
        context_text=context_text,
        key_points=key_points,
        related=related_list,
    )


@router.post("/summarize/{conversation_id}")
def summarize_conversation(
    conversation_id: str,
    session: Session = Depends(get_session),
):
    """手动触发生成对话摘要。"""
    messages = session.exec(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp.asc())
    ).all()

    if not messages:
        return {"error": "对话不存在"}

    msg_dicts = [{"role": m.role, "content": m.content} for m in messages]
    result = summarizer.generate_summary(msg_dicts)

    for msg in messages:
        msg.title = result["title"]
        msg.tags = result["tags"]
        msg.summary = result["summary"]

    session.commit()

    return {
        "conversation_id": conversation_id,
        "title": result["title"],
        "tags": result["tags"],
        "summary": result["summary"],
    }


@router.get("/conversations/{conversation_id}/related", response_model=list[RelatedConversation])
def get_related_conversations(
    conversation_id: str,
    top_k: int = Query(5, le=20),
    session: Session = Depends(get_session),
):
    """获取与当前对话相关的其他对话（基于向量相似度）。"""
    # 获取当前对话的消息
    messages = session.exec(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp.asc())
    ).all()

    if not messages:
        return []

    # 用第一条用户消息作为查询文本
    user_msgs = [m for m in messages if m.role == "user"]
    query_text = " ".join(m.content for m in user_msgs) if user_msgs else messages[0].content

    # 从 ChromaDB 查找相关对话
    related = chroma_client.find_related_conversations(
        conversation_id=conversation_id,
        query_text=query_text,
        top_k=top_k,
    )

    result = []
    for item in related:
        conv_id = item["conversation_id"]
        # 获取该对话的摘要信息
        conv_msgs = session.exec(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.timestamp.desc())
        ).all()

        if not conv_msgs:
            continue

        title = conv_msgs[0].title or conv_msgs[0].content[:50]
        platform = conv_msgs[0].platform
        latest_ts = conv_msgs[0].timestamp
        msg_count = len(conv_msgs)

        result.append(RelatedConversation(
            conversation_id=conv_id,
            title=title,
            platform=platform,
            score=item["score"],
            message_count=msg_count,
            latest_timestamp=latest_ts,
        ))

    return result


@router.get("/projects", response_model=list[ProjectGroup])
def get_projects(session: Session = Depends(get_session)):
    """获取项目聚合：基于标签重叠度自动将对话聚类为项目。"""
    # 获取所有有标签的对话（去重 conversation_id）
    all_msgs = session.exec(
        select(Message)
        .where(Message.tags.isnot(None))
        .where(Message.tags != "")
        .order_by(Message.timestamp.desc())
    ).all()

    # 按 conversation_id 去重，保留最新一条
    conv_map: dict[str, Message] = {}
    for msg in all_msgs:
        if msg.conversation_id not in conv_map:
            conv_map[msg.conversation_id] = msg

    # 提取每个对话的标签集合
    conv_tags: dict[str, set[str]] = {}
    for conv_id, msg in conv_map.items():
        tags = {t.strip().lstrip("#").strip() for t in msg.tags.split(",") if t.strip()}
        conv_tags[conv_id] = tags

    # 基于标签重叠度构建图并聚类（连通分量）
    conv_ids_list = list(conv_map.keys())
    graph: dict[str, set[str]] = {cid: set() for cid in conv_ids_list}

    for i in range(len(conv_ids_list)):
        for j in range(i + 1, len(conv_ids_list)):
            cid_a = conv_ids_list[i]
            cid_b = conv_ids_list[j]
            tags_a = conv_tags[cid_a]
            tags_b = conv_tags[cid_b]
            if not tags_a or not tags_b:
                continue
            overlap = tags_a & tags_b
            min_size = min(len(tags_a), len(tags_b))
            # 至少 2 个共同标签 或 重叠度 > 50%
            if len(overlap) >= 2 or (min_size > 0 and len(overlap) / min_size > 0.5):
                graph[cid_a].add(cid_b)
                graph[cid_b].add(cid_a)

    # DFS 找连通分量
    visited: set[str] = set()
    clusters: list[list[str]] = []

    def dfs(node: str, component: list[str]):
        visited.add(node)
        component.append(node)
        for neighbor in graph[node]:
            if neighbor not in visited:
                dfs(neighbor, component)

    for cid in conv_ids_list:
        if cid not in visited:
            component: list[str] = []
            dfs(cid, component)
            clusters.append(component)

    # 构建项目列表
    projects = []
    ungrouped_cluster = None

    for cluster in clusters:
        if len(cluster) < 2:
            # 单个对话归入"其他"
            if ungrouped_cluster is None:
                ungrouped_cluster = cluster
            else:
                ungrouped_cluster.extend(cluster)
            continue

        conversations = []
        all_tags = set()
        for conv_id in cluster:
            msg = conv_map[conv_id]
            conversations.append(RelatedConversation(
                conversation_id=conv_id,
                title=msg.title or msg.content[:50],
                platform=msg.platform,
                score=1.0,
                message_count=0,
                latest_timestamp=msg.timestamp,
            ))
            all_tags.update(conv_tags[conv_id])

        # 取出现频率最高的标签作为项目名
        tag_counter: dict[str, int] = {}
        for conv_id in cluster:
            for tag in conv_tags[conv_id]:
                tag_counter[tag] = tag_counter.get(tag, 0) + 1
        best_tag = max(tag_counter, key=tag_counter.get) if tag_counter else "未分类"

        projects.append(ProjectGroup(
            name=f"{best_tag} 相关",
            keywords=list(all_tags)[:8],
            conversations=conversations,
            total_messages=len(conversations),
        ))

    # 处理孤立对话
    if ungrouped_cluster:
        ungrouped_convs = []
        ungrouped_tags = set()
        for conv_id in ungrouped_cluster:
            msg = conv_map[conv_id]
            ungrouped_convs.append(RelatedConversation(
                conversation_id=conv_id,
                title=msg.title or msg.content[:50],
                platform=msg.platform,
                score=1.0,
                message_count=0,
                latest_timestamp=msg.timestamp,
            ))
            ungrouped_tags.update(conv_tags[conv_id])

        projects.append(ProjectGroup(
            name="其他对话",
            keywords=list(ungrouped_tags)[:8],
            conversations=ungrouped_convs,
            total_messages=len(ungrouped_convs),
        ))

    return projects


@router.get("/graph", response_model=GraphData)
def get_graph(session: Session = Depends(get_session)):
    """获取知识图谱数据：对话节点 + 标签节点 + 关联边。"""
    # 获取所有有标签的对话
    all_msgs = session.exec(
        select(Message)
        .where(Message.tags.isnot(None))
        .where(Message.tags != "")
        .order_by(Message.timestamp.desc())
    ).all()

    # 按 conversation_id 去重
    conv_map: dict[str, Message] = {}
    for msg in all_msgs:
        if msg.conversation_id not in conv_map:
            conv_map[msg.conversation_id] = msg

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    tag_counter: dict[str, int] = {}
    conv_tags: dict[str, set[str]] = {}

    # 创建节点和标签统计
    for conv_id, msg in conv_map.items():
        tags = {t.strip().lstrip("#").strip() for t in msg.tags.split(",") if t.strip()}
        conv_tags[conv_id] = tags

        # 对话节点
        title = msg.title or msg.content[:40]
        nodes.append(GraphNode(
            id=conv_id,
            type="conversation",
            label=title,
            platform=msg.platform,
            message_count=0,  # 后续可以统计
        ))

        # 标签频率统计
        for tag in tags:
            tag_counter[tag] = tag_counter.get(tag, 0) + 1

        # tag_link 边
        for tag in tags:
            edges.append(GraphEdge(
                source=conv_id,
                target=f"tag:{tag}",
                type="tag_link",
                weight=0.5,
            ))

    # 标签节点（只保留出现 >= 2 次的）
    for tag, count in tag_counter.items():
        if count >= 2:
            nodes.append(GraphNode(
                id=f"tag:{tag}",
                type="tag",
                label=f"#{tag}",
                weight=count,
            ))

    # 相似边：基于标签重叠
    conv_ids = list(conv_map.keys())
    for i in range(len(conv_ids)):
        for j in range(i + 1, len(conv_ids)):
            a, b = conv_ids[i], conv_ids[j]
            overlap = conv_tags[a] & conv_tags[b]
            if len(overlap) >= 2:
                weight = min(len(overlap) / 5, 1.0)
                edges.append(GraphEdge(
                    source=a, target=b,
                    type="similar",
                    weight=round(weight, 2),
                ))

    # 向量相似边：对每对对话计算 embedding 相似度（选取最近的前 N 对）
    # 为性能考虑，仅对标签有重叠的对话对计算
    for i in range(len(conv_ids)):
        for j in range(i + 1, len(conv_ids)):
            a, b = conv_ids[i], conv_ids[j]
            overlap = conv_tags[a] & conv_tags[b]
            if len(overlap) == 0:
                # 无标签重叠但尝试向量相似
                try:
                    msg_a = conv_map[a]
                    results = chroma_client.find_related_conversations(
                        a, (msg_a.title or msg_a.content)[:100], exclude_conv_id=None, top_k=3
                    )
                    for r in results:
                        if r["conversation_id"] == b and r["score"] > 0.5:
                            edges.append(GraphEdge(
                                source=a, target=b,
                                type="vector_similar",
                                weight=round(r["score"], 2),
                            ))
                            break
                except Exception:
                    pass

    # 去重边
    seen_edges = set()
    unique_edges = []
    for e in edges:
        key = (min(e.source, e.target), max(e.source, e.target), e.type)
        if key not in seen_edges:
            seen_edges.add(key)
            unique_edges.append(e)

    return GraphData(nodes=nodes, edges=unique_edges)


@router.get("/stats")
def get_stats(session: Session = Depends(get_session)):
    """获取统计信息。"""
    total = session.exec(select(func.count(Message.id))).one()
    platforms = session.exec(
        select(Message.platform, func.count(Message.id)).group_by(Message.platform)
    ).all()
    return {
        "total_messages": total,
        "by_platform": {p: c for p, c in platforms},
        "vector_index_count": chroma_client.get_count(),
    }

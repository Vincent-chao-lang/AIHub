"""
系统事件采集服务：接收 AI 系统运行事件，复用既有 embedding + 摘要 + 图谱管线。

设计原则：
- 复用 embedding.py / summarizer.py，零新增推理成本
- SystemEvent 存入与 message 相同的 ChromaDB 集合（ID 加 "se:" 前缀）
- error 事件同步创建 FailureSample（关键信号不丢失）
"""
import uuid
import json
import logging
from datetime import datetime, timezone

from sqlmodel import Session, select
from services.vector_store import get_vector_store
from services import summarizer
from models.operability import SystemEvent, FailureSample

logger = logging.getLogger(__name__)

# ChromaDB 中系统事件的 ID 前缀，避免与 message ID 冲突
EVENT_ID_PREFIX = "se:"


def process_system_event(
    event: SystemEvent,
    background_tasks,
    session_factory,
):
    """处理系统事件的入口函数。

    1. 派发后台任务：embedding 向量化 + 自动摘要
    2. 同步检测 error → 自动创建 FailureSample（P5 学习闭环）
    """
    # 后台异步：embedding 向量化
    background_tasks.add_task(_embed_and_index_event, event)

    # 后台异步：自动摘要
    background_tasks.add_task(_auto_summarize_event, session_factory, event.id)

    # 同步：error 事件自动进入失败样本库
    if event.status == "error":
        _auto_create_failure_sample(session_factory, event.id)


def _build_event_search_text(event: SystemEvent) -> str:
    """构造可检索的系统事件文本表示。

    将结构化字段拼接为自然语言文本，使向量搜索能跨类型命中。
    例："AI System: agent-fin-001 | Event: tool_call | Model: gpt-4o | Tools: [...]"
    """
    parts = [f"AI System: {event.ai_system_id}", f"Event: {event.event_type}"]

    if event.model_version:
        parts.append(f"Model: {event.model_version}")
    if event.retrieval_source:
        parts.append(f"Source: {event.retrieval_source}")
    if event.tool_calls:
        try:
            tools = json.loads(event.tool_calls)
            tool_names = [t.get("tool", "?") for t in tools] if isinstance(tools, list) else [str(tools)]
            parts.append(f"Tools: [{', '.join(tool_names)}]")
        except (json.JSONDecodeError, TypeError):
            parts.append(f"Tools: {event.tool_calls}")
    if event.human_approval:
        try:
            approval = json.loads(event.human_approval)
            approver = approval.get("approver", "?")
            result = approval.get("result", "?")
            parts.append(f"Approval: {approver} → {result}")
        except (json.JSONDecodeError, TypeError):
            parts.append(f"Approval: {event.human_approval}")
    if event.status:
        parts.append(f"Status: {event.status}")

    return " | ".join(parts)


def _embed_and_index_event(event: SystemEvent):
    """后台任务：为系统事件生成 embedding 并存入向量索引。

    存入与 message 相同的 ChromaDB 集合，ID 加 "se:" 前缀避免冲突。
    metadata 标记 source="system_event" 以便跨类型过滤。
    """
    try:
        search_text = _build_event_search_text(event)
        store = get_vector_store()
        store.add(
            msg_id=f"{EVENT_ID_PREFIX}{event.id}",
            content=search_text,
            metadata={
                "source": "system_event",
                "ai_system_id": event.ai_system_id,
                "event_type": event.event_type,
                "status": event.status or "",
            },
        )
        logger.info(f"系统事件已索引: {event.id} (type={event.event_type})")
    except Exception as e:
        logger.error(f"系统事件 embedding 失败: {e}")


def _auto_summarize_event(session_factory, event_id: str):
    """后台任务：为系统事件自动生成摘要（标题、标签、摘要文本）。

    复用 summarizer.generate_summary()，适配 SystemEvent 的文本格式。
    """
    try:
        with next(session_factory()) as session:
            event = session.get(SystemEvent, event_id)
            if event is None:
                logger.warning(f"摘要生成：事件不存在 {event_id}")
                return

            # 构造伪消息列表，适配 summarizer 接口
            search_text = _build_event_search_text(event)
            pseudo_messages = [
                {"role": "user", "content": search_text},
                {"role": "assistant", "content": f"事件类型: {event.event_type}, 状态: {event.status or 'N/A'}"},
            ]

            result = summarizer.generate_summary(pseudo_messages)

            if not event.title:
                event.title = result["title"]
            if not event.tags:
                event.tags = result["tags"]
            if not event.summary:
                event.summary = result["summary"]

            session.commit()
            logger.info(f"系统事件摘要已生成: {event_id}")
    except Exception as e:
        logger.error(f"系统事件摘要生成失败: {e}")


def _auto_create_failure_sample(session_factory, event_id: str):
    """同步创建 FailureSample（当系统事件 status 为 error 时）。

    检查去重：同一 source_id 不重复创建。
    """
    try:
        with next(session_factory()) as session:
            # 去重检查
            existing = session.exec(
                select(FailureSample).where(
                    FailureSample.source_type == "system_event",
                    FailureSample.source_id == event_id,
                )
            ).first()

            if existing is not None:
                logger.debug(f"FailureSample 已存在，跳过: {event_id}")
                return

            sample = FailureSample(
                id=uuid.uuid4().hex,
                source_type="system_event",
                source_id=event_id,
                failure_mode=None,
                labeled=0,
                promoted_to_regression=0,
            )
            session.add(sample)
            session.commit()
            logger.info(f"FailureSample 已自动创建: {sample.id} ← event {event_id}")
    except Exception as e:
        logger.error(f"FailureSample 自动创建失败: {e}")

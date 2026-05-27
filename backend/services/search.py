"""
语义搜索服务。

MVP 阶段使用简单的关键词匹配（不依赖 embedding API），
后续可接入 ChromaDB + embedding 模型。
"""

from sqlmodel import Session, select
from models.message import Message


def keyword_search(session: Session, query: str, limit: int = 20) -> list[Message]:
    """简单的关键词搜索，按时间倒序返回匹配的消息。"""
    keywords = query.lower().split()
    all_messages = session.exec(
        select(Message).order_by(Message.timestamp.desc())
    ).all()

    results = []
    for msg in all_messages:
        score = 0
        content_lower = msg.content.lower()
        for kw in keywords:
            if kw in content_lower:
                score += 1
        # 标题和标签匹配加权
        if msg.title:
            title_lower = msg.title.lower()
            for kw in keywords:
                if kw in title_lower:
                    score += 3
        if msg.tags:
            tags_lower = msg.tags.lower()
            for kw in keywords:
                if kw in tags_lower:
                    score += 2

        if score > 0:
            results.append((msg, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return [msg for msg, _ in results[:limit]]

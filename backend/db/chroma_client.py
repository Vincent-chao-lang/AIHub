"""
ChromaDB 向量存储客户端。

用于消息的向量索引和语义搜索。
"""

import logging
import os
from pathlib import Path

import chromadb
from chromadb.config import Settings

from services.embedding_provider import get_embedding_provider

logger = logging.getLogger(__name__)

# ChromaDB 持久化目录，可通过 CHROMA_PATH 环境变量自定义
CHROMA_PATH = Path(os.getenv("CHROMA_PATH", Path(__file__).parent.parent / ".chromadb"))
COLLECTION_NAME = "messages"

_client = None
_collection = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        CHROMA_PATH.mkdir(exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(CHROMA_PATH),
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def _get_collection() -> chromadb.Collection:
    """获取或创建消息 collection。"""
    global _collection
    if _collection is None:
        client = _get_client()
        provider = get_embedding_provider()
        dim = provider.get_dimension()

        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine", "dimension": dim},
        )
        # 检查已有 collection 的维度是否匹配
        existing_dim = _collection.metadata.get("dimension") if _collection.metadata else None
        if existing_dim and int(existing_dim) != dim:
            logger.warning(
                f"向量维度不匹配！当前 provider 维度={dim}，"
                f"已有 collection 维度={existing_dim}。"
                f"请运行 python backend/rebuild_index.py 重建索引"
            )
    return _collection


def add_message(msg_id: str, content: str, metadata: dict | None = None):
    """将消息添加到向量索引。"""
    try:
        emb = get_embedding_provider().embed_texts([content])
        collection = _get_collection()
        collection.add(
            ids=[msg_id],
            embeddings=emb,
            metadatas=[metadata or {}],
            documents=[content],
        )
        logger.debug(f"向量索引已添加: {msg_id}")
    except Exception as e:
        logger.error(f"向量索引添加失败: {e}")


def search_similar(query: str, top_k: int = 20) -> list[dict]:
    """语义搜索，返回最相似的消息列表。

    返回格式: [{"id": msg_id, "score": float, "metadata": dict}, ...]
    """
    try:
        query_emb = get_embedding_provider().embed_query(query)
        collection = _get_collection()
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
            include=["metadatas", "documents", "distances"],
        )

        items = []
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        documents = results.get("documents", [[]])[0]

        for i, msg_id in enumerate(ids):
            # cosine distance → similarity score (0~1)
            score = 1.0 - distances[i] if i < len(distances) else 0.0
            items.append({
                "id": msg_id,
                "score": round(score, 4),
                "document": documents[i] if i < len(documents) else "",
                "metadata": metadatas[i] if i < len(metadatas) else {},
            })

        return items
    except Exception as e:
        logger.error(f"向量搜索失败: {e}")
        return []


def find_related_conversations(
    conversation_id: str,
    query_text: str,
    exclude_conv_id: str | None = None,
    top_k: int = 10,
) -> list[dict]:
    """查找与给定对话相关的其他对话。

    返回格式: [{"conversation_id": str, "score": float, "matched_message": dict}, ...]
    """
    try:
        query_emb = get_embedding_provider().embed_query(query_text)
        collection = _get_collection()
        # 多拉一些结果，因为要过滤掉同一对话的消息
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=min(top_k * 5, 100),
            include=["metadatas", "documents", "distances"],
        )

        exclude_id = exclude_conv_id or conversation_id
        seen_convs = set()
        related = []

        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        documents = results.get("documents", [[]])[0]

        for i, msg_id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            conv_id = meta.get("conversation_id", "")
            if conv_id == exclude_id or conv_id in seen_convs:
                continue
            seen_convs.add(conv_id)
            score = 1.0 - distances[i] if i < len(distances) else 0.0
            related.append({
                "conversation_id": conv_id,
                "score": round(score, 4),
                "matched_message": {
                    "id": msg_id,
                    "platform": meta.get("platform", ""),
                    "content_snippet": (documents[i] if i < len(documents) else "")[:100],
                },
            })
            if len(related) >= top_k:
                break

        return related
    except Exception as e:
        logger.error(f"查找相关对话失败: {e}")
        return []


def get_count() -> int:
    """获取向量索引中的消息数量。"""
    try:
        return _get_collection().count()
    except Exception:
        return 0

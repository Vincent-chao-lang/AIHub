"""
向量存储抽象接口 + 工厂函数。

通过 VECTOR_STORE 环境变量切换后端：
  · chromadb（默认）— 零配置，本地持久化
  · pgvector        — 需要 PostgreSQL + pgvector 扩展
"""

import os
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """向量存储的抽象接口。所有后端必须实现这 4 个方法。"""

    @abstractmethod
    def add(self, msg_id: str, content: str, metadata: dict):
        """将消息内容和元数据加入向量索引。"""
        ...

    @abstractmethod
    def search(self, query: str, top_k: int = 20) -> list[dict]:
        """语义搜索，返回 [{"id": str, "score": float, "document": str, "metadata": dict}, ...]。"""
        ...

    @abstractmethod
    def find_related(
        self,
        conversation_id: str,
        query_text: str,
        exclude_conv_id: str | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """查找与指定对话相关的其他对话。"""
        ...

    @abstractmethod
    def count(self) -> int:
        """返回向量索引中的条目数。"""
        ...


def get_vector_store() -> VectorStore:
    """根据 VECTOR_STORE 环境变量返回对应的向量存储实例（单例）。"""
    global _store
    store_type = os.getenv("VECTOR_STORE", "chromadb")

    if "_store" not in globals():
        if store_type == "pgvector":
            from db.pgvector_store import PgVectorStore
            _store = PgVectorStore()
        else:
            from db.chroma_store import ChromaStore
            _store = ChromaStore()

    return _store

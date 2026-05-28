"""
ChromaDB 向量存储实现。

实现 VectorStore 接口，对 ChromaDB 的薄封装。
实际逻辑在 chroma_client.py 中。
"""

import logging
from services.vector_store import VectorStore
from db import chroma_client

logger = logging.getLogger(__name__)


class ChromaStore(VectorStore):
    """ChromaDB 向量存储后端——零配置、本地持久化。"""

    def add(self, msg_id: str, content: str, metadata: dict):
        chroma_client.add_message(msg_id, content, metadata)

    def search(self, query: str, top_k: int = 20) -> list[dict]:
        return chroma_client.search_similar(query, top_k)

    def find_related(
        self,
        conversation_id: str,
        query_text: str,
        exclude_conv_id: str | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        return chroma_client.find_related_conversations(
            conversation_id, query_text, exclude_conv_id, top_k
        )

    def count(self) -> int:
        return chroma_client.get_count()

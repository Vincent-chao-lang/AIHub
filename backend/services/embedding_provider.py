"""
Embedding 抽象接口 + 工厂函数。

通过 EMBEDDING_PROVIDER 环境变量切换后端：
  · local（默认）— 本地 sentence-transformers 模型
  · openai        — OpenAI text-embedding API
"""
import os
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# 单例缓存
_provider = None


class EmbeddingProvider(ABC):
    """Embedding 提供者的抽象接口。"""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """将文本列表转换为 embedding 向量列表。"""
        ...

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """将查询文本转换为 embedding 向量。"""
        ...

    @abstractmethod
    def get_dimension(self) -> int:
        """获取 embedding 向量维度。"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """提供者名称，用于日志/stats 展示。"""
        ...


def get_embedding_provider() -> EmbeddingProvider:
    """根据 EMBEDDING_PROVIDER 环境变量返回对应的 provider 实例（单例）。"""
    global _provider
    if _provider is not None:
        return _provider

    provider_type = os.getenv("EMBEDDING_PROVIDER", "local").lower()

    if provider_type == "openai":
        from services.embedding_providers.openai_provider import OpenAIEmbeddingProvider
        _provider = OpenAIEmbeddingProvider()
    else:
        from services.embedding import LocalEmbeddingProvider
        _provider = LocalEmbeddingProvider()

    logger.info(f"Embedding provider: {_provider.name}, 维度: {_provider.get_dimension()}")
    return _provider

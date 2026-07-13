"""
本地 Embedding 服务：使用 sentence-transformers 本地模型进行文本向量化。

模型首次加载会下载约 100MB 文件，之后缓存到本地。
通过 EMBEDDING_MODEL 环境变量可切换模型，默认 BAAI/bge-small-zh-v1.5。
"""

import os
import logging
from pathlib import Path

from services.embedding_provider import EmbeddingProvider

logger = logging.getLogger(__name__)

# 模型缓存目录
MODEL_DIR = Path(__file__).parent.parent / ".models"
DEFAULT_MODEL_NAME = "BAAI/bge-small-zh-v1.5"


class LocalEmbeddingProvider(EmbeddingProvider):
    """本地 sentence-transformers embedding 提供者。"""

    def __init__(self):
        self._model = None
        self._model_name = os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL_NAME)

    def _load_model(self):
        """懒加载 embedding 模型（首次调用时加载）。"""
        if self._model is not None:
            return self._model

        from sentence_transformers import SentenceTransformer

        MODEL_DIR.mkdir(exist_ok=True)
        logger.info(f"加载 embedding 模型: {self._model_name} ...")
        self._model = SentenceTransformer(
            self._model_name,
            cache_folder=str(MODEL_DIR),
        )
        logger.info(f"Embedding 模型加载完成，维度: {self._model.get_sentence_embedding_dimension()}")
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """将文本列表转换为 embedding 向量列表。"""
        model = self._load_model()
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """将查询文本转换为 embedding 向量（自动添加 BGE 查询前缀）。"""
        model = self._load_model()
        embedding = model.encode(
            [f"为这个句子生成表示以用于检索相关文章：{query}"],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embedding[0].tolist()

    def get_dimension(self) -> int:
        """获取 embedding 向量维度。"""
        model = self._load_model()
        return model.get_sentence_embedding_dimension()

    @property
    def name(self) -> str:
        return f"local:{self._model_name}"


# ── 向后兼容的模块级函数 ──

_default_provider = None


def _get_default_provider() -> LocalEmbeddingProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = LocalEmbeddingProvider()
    return _default_provider


def embed_texts(texts: list[str]) -> list[list[float]]:
    """将文本列表转换为 embedding 向量列表。（向后兼容函数）"""
    return _get_default_provider().embed_texts(texts)


def embed_query(query: str) -> list[float]:
    """将查询文本转换为 embedding 向量。（向后兼容函数）"""
    return _get_default_provider().embed_query(query)


def get_embedding_dim() -> int:
    """获取 embedding 向量维度。（向后兼容函数）"""
    return _get_default_provider().get_dimension()

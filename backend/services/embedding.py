"""
Embedding 服务：使用 BGE-small 本地模型进行文本向量化。

模型首次加载会下载约 100MB 文件，之后缓存到本地。
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 模型缓存目录
MODEL_DIR = Path(__file__).parent.parent / ".models"
MODEL_NAME = "BAAI/bge-small-zh-v1.5"

_embedding_model = None


def _load_model():
    """懒加载 embedding 模型（首次调用时加载）。"""
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    from sentence_transformers import SentenceTransformer

    MODEL_DIR.mkdir(exist_ok=True)
    logger.info(f"加载 embedding 模型: {MODEL_NAME} ...")
    _embedding_model = SentenceTransformer(
        MODEL_NAME,
        cache_folder=str(MODEL_DIR),
    )
    logger.info(f"Embedding 模型加载完成，维度: {_embedding_model.get_sentence_embedding_dimension()}")
    return _embedding_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """将文本列表转换为 embedding 向量列表。"""
    model = _load_model()
    # BGE 模型推荐在查询前加前缀以提升效果
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """将查询文本转换为 embedding 向量（自动添加 BGE 查询前缀）。"""
    model = _load_model()
    # BGE 模型查询时添加 instruction prefix
    embedding = model.encode(
        [f"为这个句子生成表示以用于检索相关文章：{query}"],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embedding[0].tolist()


def get_embedding_dim() -> int:
    """获取 embedding 向量维度。"""
    model = _load_model()
    return model.get_sentence_embedding_dimension()

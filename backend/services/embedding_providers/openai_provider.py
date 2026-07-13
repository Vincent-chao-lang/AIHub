"""
OpenAI Embedding 提供者。

支持 text-embedding-3-small / text-embedding-3-large 等模型。
通过 OPENAI_API_KEY 和 OPENAI_BASE_URL 配置连接。
"""

import os
import logging
from services.embedding_provider import EmbeddingProvider

logger = logging.getLogger(__name__)

# text-embedding-3 系列默认维度
_DEFAULT_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding API 提供者。"""

    def __init__(self):
        self._model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self._dim = int(os.getenv("EMBEDDING_DIM", "0")) or None

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("EMBEDDING_PROVIDER=openai 时，必须设置 OPENAI_API_KEY 环境变量")

        base_url = os.getenv("OPENAI_BASE_URL")
        try:
            from openai import OpenAI
            if base_url:
                self._client = OpenAI(api_key=api_key, base_url=base_url)
            else:
                self._client = OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("使用 OpenAI embedding 需要安装 openai 包: pip install openai")

        logger.info(f"OpenAI embedding 已配置: model={self._model}, dim={self._dim or self.get_dimension()}")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量生成 embedding 向量。"""
        kwargs = {"model": self._model, "input": texts}
        if self._dim:
            kwargs["dimensions"] = self._dim

        try:
            resp = self._client.embeddings.create(**kwargs)
            # 按 input 顺序排列结果
            return [d.embedding for d in resp.data]
        except Exception as e:
            logger.error(f"OpenAI embedding 失败: {e}")
            raise

    def embed_query(self, query: str) -> list[float]:
        """单条查询 embedding。"""
        return self.embed_texts([query])[0]

    def get_dimension(self) -> int:
        """获取 embedding 向量维度。"""
        if self._dim:
            return self._dim
        # 从模型名推断维度
        return _DEFAULT_DIMENSIONS.get(self._model, 1536)

    @property
    def name(self) -> str:
        dim_info = f"@{self._dim}" if self._dim else ""
        return f"openai:{self._model}{dim_info}"

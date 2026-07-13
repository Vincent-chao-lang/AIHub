"""
pgvector 向量存储实现。

使用 PostgreSQL 的 pgvector 扩展存储向量，配合 SQLModel/SQLAlchemy。
启用条件：VECTOR_STORE=pgvector + DATABASE_URL 指向 PostgreSQL。
"""

import json
import logging
from typing import Optional

from sqlmodel import SQLModel, Field, Session, text
from sqlalchemy import Column

from services.vector_store import VectorStore
from services.embedding_provider import get_embedding_provider
from db.database import engine

logger = logging.getLogger(__name__)


class VectorMessage(SQLModel, table=True):
    """pgvector 向量索引表。"""

    __tablename__ = "vector_messages"

    id: str = Field(primary_key=True)
    platform: str = ""
    conversation_id: str = Field(default="", index=True)
    role: str = ""
    content: str = ""
    metadata_json: str = "{}"  # JSON 字符串，存储额外元数据


def _ensure_extension_and_column():
    """确保 pgvector 扩展和向量列存在（维度根据当前 provider 动态设置）。"""
    provider = get_embedding_provider()
    dim = provider.get_dimension()

    with Session(engine) as session:
        session.exec(text("CREATE EXTENSION IF NOT EXISTS vector"))
        session.commit()

    # 检查已有向量列的维度是否匹配
    with Session(engine) as session:
        try:
            result = session.exec(text(
                "SELECT atttypmod FROM pg_attribute "
                "WHERE attrelid = 'vector_messages'::regclass "
                "AND attname = 'embedding' AND NOT attisdropped"
            )).first()
            if result is not None and result[0] > 0:
                # pgvector 的 atttypmod = dim + 4，所以实际维度 = atttypmod - 4
                existing_dim = result[0] - 4
                if existing_dim != dim:
                    logger.warning(
                        f"向量维度不匹配！当前 provider 维度={dim}，"
                        f"已有列维度={existing_dim}。"
                        f"请运行 python backend/rebuild_index.py 重建索引"
                    )
        except Exception:
            pass

    # 使用原生 SQL 添加向量列（如果不存在）
    with Session(engine) as session:
        try:
            session.exec(text(
                f"ALTER TABLE vector_messages ADD COLUMN IF NOT EXISTS "
                f"embedding vector({dim})"
            ))
            session.commit()
        except Exception:
            session.rollback()

    # 创建 HNSW 索引（如果不存在）
    with Session(engine) as session:
        try:
            session.exec(text(
                "CREATE INDEX IF NOT EXISTS idx_vector_messages_embedding "
                "ON vector_messages USING hnsw (embedding vector_cosine_ops)"
            ))
            session.commit()
        except Exception:
            session.rollback()


class PgVectorStore(VectorStore):
    """pgvector 向量存储后端——适合已有 PostgreSQL 的团队。"""

    def __init__(self):
        _ensure_extension_and_column()

    def add(self, msg_id: str, content: str, metadata: dict | None = None):
        try:
            meta = metadata or {}
            emb = get_embedding_provider().embed_texts([content])[0]
            emb_str = f"[{','.join(str(v) for v in emb)}]"

            with Session(engine) as session:
                # 先删除旧记录（如果存在）
                session.exec(
                    text("DELETE FROM vector_messages WHERE id = :id"),
                    {"id": msg_id},
                )
                # 插入新记录
                session.exec(
                    text(
                        "INSERT INTO vector_messages "
                        "(id, platform, conversation_id, role, content, metadata_json, embedding) "
                        "VALUES (:id, :platform, :conv_id, :role, :content, :meta, :emb)"
                    ),
                    {
                        "id": msg_id,
                        "platform": meta.get("platform", ""),
                        "conv_id": meta.get("conversation_id", ""),
                        "role": meta.get("role", ""),
                        "content": content,
                        "meta": json.dumps(meta, ensure_ascii=False),
                        "emb": emb_str,
                    },
                )
                session.commit()
            logger.debug(f"pgvector 索引已添加: {msg_id}")
        except Exception as e:
            logger.error(f"pgvector 添加失败: {e}")

    def search(self, query: str, top_k: int = 20) -> list[dict]:
        try:
            query_emb = get_embedding_provider().embed_query(query)
            emb_str = f"[{','.join(str(v) for v in query_emb)}]"

            with Session(engine) as session:
                result = session.exec(
                    text(
                        "SELECT id, content, platform, conversation_id, role, metadata_json, "
                        "1 - (embedding <=> :emb) AS score "
                        "FROM vector_messages "
                        "ORDER BY embedding <=> :emb "
                        "LIMIT :limit"
                    ),
                    {"emb": emb_str, "limit": top_k},
                )
                items = []
                for row in result:
                    items.append({
                        "id": row[0],
                        "score": round(float(row[6]), 4),
                        "document": row[1],
                        "metadata": {
                            "platform": row[2],
                            "conversation_id": row[3],
                            "role": row[4],
                        },
                    })
                return items
        except Exception as e:
            logger.error(f"pgvector 搜索失败: {e}")
            return []

    def find_related(
        self,
        conversation_id: str,
        query_text: str,
        exclude_conv_id: str | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        try:
            query_emb = get_embedding_provider().embed_query(query_text)
            emb_str = f"[{','.join(str(v) for v in query_emb)}]"
            exclude_id = exclude_conv_id or conversation_id

            with Session(engine) as session:
                result = session.exec(
                    text(
                        "SELECT DISTINCT ON (conversation_id) "
                        "conversation_id, id, content, platform, "
                        "1 - (embedding <=> :emb) AS score "
                        "FROM vector_messages "
                        "WHERE conversation_id != :exclude "
                        "ORDER BY conversation_id, embedding <=> :emb "
                        "LIMIT :limit"
                    ),
                    {
                        "emb": emb_str,
                        "exclude": exclude_id,
                        "limit": top_k * 5,
                    },
                )
                related = []
                for row in result:
                    related.append({
                        "conversation_id": row[0],
                        "score": round(float(row[4]), 4),
                        "matched_message": {
                            "id": row[1],
                            "platform": row[3],
                            "content_snippet": (row[2] or "")[:100],
                        },
                    })
                    if len(related) >= top_k:
                        break

                # 按分数排序
                related.sort(key=lambda x: x["score"], reverse=True)
                return related[:top_k]
        except Exception as e:
            logger.error(f"pgvector 查找相关失败: {e}")
            return []

    def count(self) -> int:
        try:
            with Session(engine) as session:
                result = session.exec(text("SELECT COUNT(*) FROM vector_messages"))
                return result.one()
        except Exception:
            return 0

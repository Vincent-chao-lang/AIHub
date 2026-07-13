#!/usr/bin/env python3
"""
全量重建向量索引脚本。

用途：
  - 切换 embedding provider 后维度变化时，重建所有向量索引
  - 修复向量索引数据损坏问题

用法：
  python backend/rebuild_index.py          # 交互确认
  python backend/rebuild_index.py --yes    # 跳过确认
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# 确保 backend/ 在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import Session, select, func
from db.database import engine, init_db
from models.message import Message
from services.embedding_provider import get_embedding_provider
from services.vector_store import get_vector_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rebuild_index")


def main():
    parser = argparse.ArgumentParser(description="全量重建向量索引")
    parser.add_argument("--yes", "-y", action="store_true", help="跳过确认提示")
    args = parser.parse_args()

    # 初始化数据库
    init_db()
    provider = get_embedding_provider()
    store = get_vector_store()

    dim = provider.get_dimension()
    logger.info(f"Embedding provider: {provider.name}")
    logger.info(f"向量维度: {dim}")

    # 读取所有消息
    with Session(engine) as session:
        total = session.exec(select(func.count()).select_from(Message)).one()
        logger.info(f"数据库消息总数: {total}")

        if total == 0:
            logger.info("没有消息需要重建索引，退出")
            return

        messages = session.exec(
            select(Message).order_by(Message.timestamp.asc())
        ).all()

    if not args.yes:
        print(f"\n即将重建 {len(messages)} 条消息的向量索引")
        print(f"Provider: {provider.name}, 维度: {dim}")
        print(f"向量存储类型: {os.getenv('VECTOR_STORE', 'chromadb')}")
        resp = input("\n确认重建？这将清空现有向量索引 [y/N]: ")
        if resp.strip().lower() not in ("y", "yes"):
            print("已取消")
            return

    # 清空现有索引
    logger.info("清空现有向量索引...")
    _clear_index()

    # 重新 embedding 并索引
    logger.info(f"开始重建 {len(messages)} 条消息的向量索引...")
    for i, msg in enumerate(messages):
        try:
            store.add(
                msg_id=msg.id,
                content=msg.content,
                metadata={
                    "platform": msg.platform,
                    "conversation_id": msg.conversation_id,
                    "role": msg.role,
                },
            )
            if (i + 1) % 50 == 0:
                logger.info(f"进度: {i + 1}/{len(messages)}")
        except Exception as e:
            logger.error(f"消息 {msg.id} 索引失败: {e}")
            continue

    # 验证
    final_count = store.count()
    logger.info(f"重建完成！向量索引条目数: {final_count}")
    if final_count != len(messages):
        logger.warning(
            f"条目数不匹配：数据库 {len(messages)} vs 向量索引 {final_count}"
        )


def _clear_index():
    """清空现有向量索引。"""
    store_type = os.getenv("VECTOR_STORE", "chromadb")

    if store_type == "pgvector":
        from sqlmodel import text
        with Session(engine) as session:
            session.exec(text("DELETE FROM vector_messages"))
            session.commit()
        logger.info("pgvector 索引已清空")
    else:
        # ChromaDB: 删除 collection 并重置缓存
        from db.chroma_client import _get_client, COLLECTION_NAME
        try:
            client = _get_client()
            client.delete_collection(COLLECTION_NAME)
            logger.info("ChromaDB collection 已删除")
        except Exception as e:
            logger.warning(f"删除 ChromaDB collection 失败: {e}")

        # 重置模块级缓存，下次访问时会用新维度重建 collection
        import db.chroma_client as chroma_module
        chroma_module._collection = None


if __name__ == "__main__":
    main()

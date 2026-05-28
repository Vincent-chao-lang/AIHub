import os
from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine

# 默认使用 SQLite，可通过 DATABASE_URL 环境变量切换到 PostgreSQL
DB_PATH = Path(__file__).parent.parent / "aihub.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

# PostgreSQL 需要额外参数
if DATABASE_URL.startswith("postgresql"):
    engine = create_engine(DATABASE_URL, echo=False, pool_size=5)
else:
    engine = create_engine(DATABASE_URL, echo=False)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

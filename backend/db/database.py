import os
from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine

# 默认使用 SQLite（路径相对于 backend/ 目录），可通过 DATABASE_URL 环境变量切换
_BASE_DIR = Path(__file__).parent.parent
_DEFAULT_DB = _BASE_DIR / "aihub.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_DB}")

# 如果是 SQLite 且路径是相对路径，转为绝对路径（相对于 backend/）
if DATABASE_URL.startswith("sqlite"):
    prefix = "sqlite:///"
    path_str = DATABASE_URL[len(prefix):]
    db_path = Path(path_str)
    if not db_path.is_absolute():
        db_path = _BASE_DIR / db_path
    DATABASE_URL = f"sqlite:///{db_path}"

if DATABASE_URL.startswith("postgresql"):
    engine = create_engine(DATABASE_URL, echo=False, pool_size=5)
else:
    engine = create_engine(DATABASE_URL, echo=False)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

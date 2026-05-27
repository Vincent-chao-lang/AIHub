from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine

DB_PATH = Path(__file__).parent.parent / "aihub.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL, echo=False)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

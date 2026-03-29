from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


def _normalize_sqlite_path(url: str) -> str:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url

    raw_path = url[len(prefix) :]
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = Path(__file__).resolve().parents[2] / raw_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}{db_path.as_posix()}"


class Base(DeclarativeBase):
    pass


engine = create_engine(
    _normalize_sqlite_path(settings.database_url),
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema() -> None:
    with engine.begin() as connection:
        if engine.dialect.name != "sqlite":
            return

        columns = connection.execute(text("PRAGMA table_info(messages)")).mappings().all()
        column_names = {str(item["name"]) for item in columns}
        if "sources_json" not in column_names:
            connection.execute(text("ALTER TABLE messages ADD COLUMN sources_json TEXT"))
        if "image_context" not in column_names:
            connection.execute(text("ALTER TABLE messages ADD COLUMN image_context TEXT"))

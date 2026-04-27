from threading import Lock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ..core.config import settings


class Base(DeclarativeBase):
    pass


def _validate_database_backend(dialect_name: str) -> None:
    if dialect_name == "postgresql":
        return
    if dialect_name == "sqlite":
        raise RuntimeError(
            "SQLite startup support has been removed. Configure PostgreSQL + pgvector "
            "and migrate the schema with Alembic before starting the backend."
        )
    raise RuntimeError(
        f"Unsupported database backend '{dialect_name}'. "
        "Configure PostgreSQL + pgvector for Chatchat."
    )


DATABASE_URL = settings.database_url
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
_schema_lock = Lock()
_schema_ready = False


def initialize_storage() -> None:
    global _schema_ready
    if _schema_ready:
        return

    with _schema_lock:
        if _schema_ready:
            return

        from . import models as _models  # noqa: F401

        _validate_database_backend(engine.dialect.name)
        if engine.dialect.name == "postgresql":
            from .bootstrap import upgrade_alembic_head

            upgrade_alembic_head()
        with engine.connect() as connection:
            vector_extension_ready = connection.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            ).scalar()
        if vector_extension_ready != 1:
            raise RuntimeError(
                "pgvector extension is not available in the configured database. "
                "Run Alembic migrations against PostgreSQL before starting the backend."
            )
        _schema_ready = True


def get_db():
    if not _schema_ready:
        initialize_storage()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

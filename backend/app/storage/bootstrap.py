from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy.exc import DBAPIError
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from ..core.config import BASE_DIR, settings
from . import models as _models  # noqa: F401
from .database import Base, engine

_HEAD_SENTINEL_TABLES = {
    "users",
    "conversations",
    "messages",
    "message_attachments",
    "knowledge_documents",
    "knowledge_chunks",
    "runs",
    "run_events",
    "provider_file_refs",
}


def _table_names() -> set[str]:
    return set(inspect(engine).get_table_names())


def _column_names(table_name: str) -> set[str]:
    return {str(column["name"]) for column in inspect(engine).get_columns(table_name)}


def _configure_alembic() -> Config:
    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def upgrade_alembic_head() -> None:
    command.upgrade(_configure_alembic(), "head")


def ensure_postgres_extensions(connection: Connection) -> None:
    if connection.dialect.name != "postgresql":
        return

    connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))


def ensure_postgres_knowledge_indexes(connection: Connection) -> None:
    if connection.dialect.name != "postgresql":
        return

    ensure_postgres_extensions(connection)
    existing_tables = set(inspect(connection).get_table_names())
    if "knowledge_chunks" not in existing_tables:
        return

    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_user_path_chunk_index
            ON knowledge_chunks (user_id, path, chunk_index)
            """
        )
    )
    try:
        with connection.begin_nested():
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_ivfflat
                    ON knowledge_chunks
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                    """
                )
            )
    except DBAPIError as exc:
        message = str(getattr(exc, "orig", exc)).lower()
        if "does not have dimensions" not in message:
            raise
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_search_text_trgm
            ON knowledge_chunks
            USING gin (
                lower(
                    coalesce(path, '')
                    || ' '
                    || coalesce(directory, '')
                    || ' '
                    || coalesce(heading, '')
                    || ' '
                    || coalesce(tags_json, '')
                    || ' '
                    || coalesce(content, '')
                ) gin_trgm_ops
            )
            """
        )
    )


def stamp_alembic_head() -> None:
    command.stamp(_configure_alembic(), "head")


def database_is_empty() -> bool:
    return not (_table_names() - {"alembic_version"})


def schema_looks_like_head() -> bool:
    table_names = _table_names()
    if not _HEAD_SENTINEL_TABLES.issubset(table_names):
        return False

    attachment_columns = _column_names("message_attachments")
    knowledge_chunk_columns = _column_names("knowledge_chunks")

    return (
        "upstream_file_id" not in attachment_columns
        and "embedding" in knowledge_chunk_columns
        and "embedding_json" not in knowledge_chunk_columns
    )


def bootstrap_empty_postgres_database_from_models() -> bool:
    if engine.dialect.name != "postgresql":
        return False
    if not database_is_empty():
        return False

    upgrade_alembic_head()
    return True


def stamp_existing_head_like_schema() -> bool:
    if engine.dialect.name != "postgresql":
        return False
    table_names = _table_names()
    if not table_names or "alembic_version" in table_names:
        return False

    upgrade_alembic_head()
    return True

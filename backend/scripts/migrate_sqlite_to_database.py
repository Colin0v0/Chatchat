from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, inspect, select, text

from app.core.config import BASE_DIR, settings
from app.providers import resolve_model_profile
from app.storage.bootstrap import bootstrap_empty_postgres_database_from_models, stamp_existing_head_like_schema
from app.storage.database import Base, SessionLocal, engine
from app.storage.models import MessageAttachment, ProviderFileRef

TABLE_ORDER = [
    "users",
    "user_sessions",
    "conversations",
    "messages",
    "message_attachments",
    "memory_items",
    "memory_documents",
    "knowledge_documents",
    "knowledge_chunks",
    "debate_sessions",
    "debate_participants",
    "debate_turns",
    "debate_judge_decisions",
]

_SOURCE_ID_CACHE: dict[str, set[int]] = {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate legacy SQLite data into the configured database.")
    parser.add_argument(
        "--source-sqlite",
        default=str(PROJECT_ROOT / "storage" / "app.db"),
        help="Path to the legacy SQLite database file.",
    )
    parser.add_argument(
        "--truncate-target",
        action="store_true",
        help="Clear target tables before importing.",
    )
    return parser.parse_args()


def _resolve_path(raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return (BASE_DIR / candidate).resolve()


def _run_alembic_upgrade() -> None:
    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")


def _ensure_target_ready() -> None:
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)
    else:
        if bootstrap_empty_postgres_database_from_models():
            return
        if stamp_existing_head_like_schema():
            return
        _run_alembic_upgrade()


def _table_has_rows(table_name: str) -> bool:
    with engine.begin() as connection:
        result = connection.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
        return int(result.scalar() or 0) > 0


def _clear_target() -> None:
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            joined = ", ".join(f'"{table_name}"' for table_name in reversed(TABLE_ORDER))
            connection.execute(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE"))
            connection.execute(text('TRUNCATE TABLE "provider_file_refs" RESTART IDENTITY CASCADE'))
            connection.execute(text('TRUNCATE TABLE "run_events" RESTART IDENTITY CASCADE'))
            connection.execute(text('TRUNCATE TABLE "runs" RESTART IDENTITY CASCADE'))
            return

    with SessionLocal() as session:
        for table_name in reversed(["provider_file_refs", "run_events", "runs", *TABLE_ORDER]):
            session.execute(Base.metadata.tables[table_name].delete())
        session.commit()


def _source_columns(connection: sqlite3.Connection, table_name: str) -> list[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [str(row[1]) for row in rows]


def _source_id_set(connection: sqlite3.Connection, table_name: str) -> set[int]:
    cached = _SOURCE_ID_CACHE.get(table_name)
    if cached is not None:
        return cached

    rows = connection.execute(f'SELECT id FROM "{table_name}"').fetchall()
    normalized = {
        int(row[0])
        for row in rows
        if row and row[0] is not None
    }
    _SOURCE_ID_CACHE[table_name] = normalized
    return normalized


def _clear_invalid_foreign_key(
    payload: dict[str, object],
    *,
    column_name: str,
    valid_ids: set[int],
) -> bool:
    raw_value = payload.get(column_name)
    if raw_value is None:
        return False

    try:
        normalized = int(raw_value)
    except (TypeError, ValueError):
        payload[column_name] = None
        return True

    if normalized in valid_ids:
        return False

    payload[column_name] = None
    return True


def _sanitize_payloads(
    source: sqlite3.Connection,
    *,
    table_name: str,
    payloads: list[dict[str, object]],
) -> int:
    sanitized = 0

    if table_name == "memory_items":
        valid_message_ids = _source_id_set(source, "messages")
        valid_conversation_ids = _source_id_set(source, "conversations")
        valid_attachment_ids = _source_id_set(source, "message_attachments")

        for payload in payloads:
            if _clear_invalid_foreign_key(
                payload,
                column_name="conversation_id",
                valid_ids=valid_conversation_ids,
            ):
                sanitized += 1
            if _clear_invalid_foreign_key(
                payload,
                column_name="source_user_message_id",
                valid_ids=valid_message_ids,
            ):
                sanitized += 1
            if _clear_invalid_foreign_key(
                payload,
                column_name="source_assistant_message_id",
                valid_ids=valid_message_ids,
            ):
                sanitized += 1
            if _clear_invalid_foreign_key(
                payload,
                column_name="source_attachment_id",
                valid_ids=valid_attachment_ids,
            ):
                sanitized += 1

    return sanitized


def _copy_table(source: sqlite3.Connection, table_name: str) -> int:
    source.row_factory = sqlite3.Row
    source_columns = _source_columns(source, table_name)
    target_table = Base.metadata.tables[table_name]
    insertable_columns = [column for column in target_table.columns.keys() if column in source_columns]
    if table_name == "knowledge_chunks" and "embedding" in target_table.columns.keys() and "embedding_json" in source_columns:
        insertable_columns = [column for column in insertable_columns if column != "embedding"]
    if not insertable_columns:
        if table_name != "knowledge_chunks":
            return 0

    rows = source.execute(f'SELECT * FROM "{table_name}"').fetchall()
    payloads = [{column: row[column] for column in insertable_columns} for row in rows]
    if table_name == "knowledge_chunks":
        for payload, row in zip(payloads, rows, strict=False):
            raw_embedding = row["embedding"] if "embedding" in source_columns else row["embedding_json"]
            if isinstance(raw_embedding, str):
                try:
                    payload["embedding"] = json.loads(raw_embedding)
                except json.JSONDecodeError:
                    payload["embedding"] = []
            elif isinstance(raw_embedding, list):
                payload["embedding"] = raw_embedding
            else:
                payload["embedding"] = []
    sanitized_count = _sanitize_payloads(source, table_name=table_name, payloads=payloads)
    if not payloads:
        return 0

    with engine.begin() as connection:
        connection.execute(target_table.insert(), payloads)
    if sanitized_count:
        print(f"- sanitized {sanitized_count} invalid foreign-key values while copying {table_name}")
    return len(payloads)


def _sync_postgres_sequences() -> None:
    if engine.dialect.name != "postgresql":
        return

    inspector = inspect(engine)
    with engine.begin() as connection:
        for table_name in ["provider_file_refs", "run_events", "runs", *TABLE_ORDER]:
            pk = inspector.get_pk_constraint(table_name).get("constrained_columns") or []
            if len(pk) != 1:
                continue
            pk_name = pk[0]
            connection.execute(
                text(
                    """
                    SELECT setval(
                      pg_get_serial_sequence(:table_name, :column_name),
                      COALESCE((SELECT MAX(%(column)s) FROM %(table)s), 1),
                      true
                    )
                    """
                    .replace("%(column)s", f'"{pk_name}"')
                    .replace("%(table)s", f'"{table_name}"')
                ),
                {"table_name": table_name, "column_name": pk_name},
            )


def _base_url_hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().rstrip("/").encode("utf-8")).hexdigest()


def _migrate_provider_file_refs(source: sqlite3.Connection) -> int:
    rows = source.execute(
        """
        SELECT
          ma.id AS attachment_id,
          ma.upstream_file_id AS upstream_file_id,
          c.model AS model_id
        FROM message_attachments ma
        JOIN messages m ON m.id = ma.message_id
        JOIN conversations c ON c.id = m.conversation_id
        WHERE ma.upstream_file_id IS NOT NULL AND TRIM(ma.upstream_file_id) != ''
        """
    ).fetchall()
    if not rows:
        return 0

    created = 0
    with SessionLocal() as session:
        attachment_ids = [int(row[0]) for row in rows]
        attachments = {
            attachment.id: attachment
            for attachment in session.scalars(
                select(MessageAttachment).where(MessageAttachment.id.in_(attachment_ids))
            ).all()
        }
        for attachment_id, upstream_file_id, model_id in rows:
            attachment = attachments.get(int(attachment_id))
            if attachment is None:
                continue
            profile = resolve_model_profile(str(model_id))
            if profile is None or profile.provider_family != "openai" or not profile.file_base_url:
                continue
            base_hash = _base_url_hash(profile.file_base_url)
            exists = session.scalar(
                select(func.count(ProviderFileRef.id)).where(
                    ProviderFileRef.attachment_id == attachment.id,
                    ProviderFileRef.provider_family == profile.provider_family,
                    ProviderFileRef.base_url_hash == base_hash,
                )
            )
            if exists:
                continue
            session.add(
                ProviderFileRef(
                    attachment_id=attachment.id,
                    provider_family=profile.provider_family,
                    base_url_hash=base_hash,
                    remote_file_id=str(upstream_file_id),
                    remote_purpose="user_data",
                )
            )
            created += 1
        session.commit()
    return created


def main() -> None:
    args = parse_args()
    source_path = _resolve_path(args.source_sqlite)
    if not source_path.exists():
        raise SystemExit(f"Source SQLite database does not exist: {source_path}")

    print(f"Source SQLite: {source_path}")
    print(f"Target database: {engine.url}")
    print(f"Truncate target: {'yes' if args.truncate_target else 'no'}")

    _ensure_target_ready()

    if any(_table_has_rows(table_name) for table_name in TABLE_ORDER) and not args.truncate_target:
        raise SystemExit("Target database already contains data. Re-run with --truncate-target if you want to replace it.")

    if args.truncate_target:
        _clear_target()

    source = sqlite3.connect(str(source_path))
    try:
        copied_counts: dict[str, int] = {}
        for table_name in TABLE_ORDER:
            copied_counts[table_name] = _copy_table(source, table_name)
        provider_file_ref_count = _migrate_provider_file_refs(source)
    finally:
        source.close()

    _sync_postgres_sequences()

    print("Data migration completed.")
    for table_name in TABLE_ORDER:
        print(f"- {table_name}: {copied_counts.get(table_name, 0)} rows")
    print(f"- provider_file_refs: {provider_file_ref_count} rows")


if __name__ == "__main__":
    main()

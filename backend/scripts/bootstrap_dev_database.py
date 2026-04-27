from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.storage.bootstrap import (  # noqa: E402
    bootstrap_empty_postgres_database_from_models,
    database_is_empty,
    stamp_existing_head_like_schema,
    upgrade_alembic_head,
)
from app.storage.database import engine  # noqa: E402
from sqlalchemy import inspect  # noqa: E402


def main() -> int:
    if engine.dialect.name != "postgresql":
        raise SystemExit("Development bootstrap only supports PostgreSQL databases.")

    if bootstrap_empty_postgres_database_from_models():
        print("Migrated empty PostgreSQL database to Alembic head.")
        return 0

    if stamp_existing_head_like_schema():
        print("Migrated existing unversioned PostgreSQL schema to Alembic head.")
        return 0

    table_names = set(inspect(engine).get_table_names())
    if "alembic_version" in table_names:
        upgrade_alembic_head()
        print("Development database already contains Alembic-managed tables; upgraded to Alembic head.")
        return 0

    if database_is_empty():
        raise SystemExit("Development database is empty but bootstrap did not complete.")

    raise SystemExit(
        "Development database contains a partial unmanaged schema. "
        "Recreate the dev PostgreSQL volume and run the bootstrap again."
    )


if __name__ == "__main__":
    raise SystemExit(main())

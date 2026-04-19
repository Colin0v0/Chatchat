from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://chatchat_dev:chatchat_dev@127.0.0.1:5433/chatchat_dev",
)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update a Chatchat account.")
    parser.add_argument("--username", required=True, help="Account username")
    parser.add_argument("--password", help="Account password. If omitted, one will be generated.")
    parser.add_argument(
        "--database-url",
        default=DEFAULT_DATABASE_URL,
        help=(
            "Database URL used by this script. "
            "Default points to project root storage/app.db."
        ),
    )
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Update password if the account already exists.",
    )
    parser.add_argument(
        "--take-ownership-of-orphans",
        action="store_true",
        help="Assign legacy conversations and memories without owner to this account.",
    )
    parser.add_argument(
        "--allow-live-backend",
        action="store_true",
        help="Allow running even when chatchat-backend container is up.",
    )
    return parser.parse_args()


def _is_backend_container_running() -> bool:
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "name=^chatchat-backend$",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return "chatchat-backend" in (result.stdout or "")


def main() -> int:
    args = parse_args()
    password = args.password or secrets.token_urlsafe(12)
    os.environ["DATABASE_URL"] = args.database_url
    if (
        args.database_url.startswith("sqlite:///")
        and _is_backend_container_running()
        and not args.allow_live_backend
    ):
        raise SystemExit(
            "Detected running chatchat-backend container. "
            "Stop backend before running create_user.py to avoid SQLite lock/index corruption. "
            "If you still want to continue, pass --allow-live-backend."
        )

    from app.auth import create_user, get_user_by_username, set_user_password
    from app.storage.bootstrap import bootstrap_empty_postgres_database_from_models, stamp_existing_head_like_schema
    from app.storage.database import Base, SessionLocal, engine
    from app.storage.models import Conversation, MemoryItem

    if engine.dialect.name == "postgresql":
        if not bootstrap_empty_postgres_database_from_models():
            stamp_existing_head_like_schema()
    else:
        Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = get_user_by_username(db, args.username)
        if user is None:
            user = create_user(
                db=db,
                username=args.username,
                password=password,
            )
            action = "created"
        else:
            if not args.reset_password:
                raise SystemExit("User already exists. Pass --reset-password to update the password.")
            user = set_user_password(
                db=db,
                user=user,
                password=password,
            )
            action = "updated"

        if args.take_ownership_of_orphans:
            claimed_conversations = (
                db.query(Conversation)
                .filter(Conversation.user_id.is_(None))
                .update({Conversation.user_id: user.id}, synchronize_session=False)
            )
            claimed_memories = (
                db.query(MemoryItem)
                .filter(MemoryItem.user_id.is_(None))
                .update({MemoryItem.user_id: user.id}, synchronize_session=False)
            )
            db.commit()
        else:
            claimed_conversations = 0
            claimed_memories = 0

        print(f"User {action}: {user.username}")
        print(f"Password: {password}")
        print(f"Claimed conversations: {claimed_conversations}")
        print(f"Claimed memories: {claimed_memories}")
        print(f"Database URL: {engine.url}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

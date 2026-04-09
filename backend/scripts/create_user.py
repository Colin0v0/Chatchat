from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.auth import create_user, get_user_by_username, set_user_password
from app.storage.database import Base, SessionLocal, engine, ensure_schema
from app.storage.models import Conversation, MemoryItem


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update a Chatchat account.")
    parser.add_argument("--username", required=True, help="Account username")
    parser.add_argument("--password", help="Account password. If omitted, one will be generated.")
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    password = args.password or secrets.token_urlsafe(12)

    Base.metadata.create_all(bind=engine)
    ensure_schema()
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
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

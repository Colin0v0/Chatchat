import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth.service import (
    AuthenticationFailed,
    AuthenticationFailureCode,
    PasswordChangeFailed,
    PasswordChangeFailureCode,
    apply_session_cookie,
    authenticate_user,
    change_user_password,
    create_user,
    create_user_session,
    invalidate_user_session,
    resolve_request_user,
)
from app.storage.database import Base
from app.storage.models import UserSession
from fastapi import Response


class AuthServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db: Session = self.session_factory()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_create_user_and_authenticate(self):
        user = create_user(db=self.db, username="alice", password="secret123")

        authenticated = authenticate_user(db=self.db, username="alice", password="secret123")

        self.assertEqual(authenticated.id, user.id)

        with self.assertRaises(AuthenticationFailed) as wrong_password:
            authenticate_user(db=self.db, username="alice", password="wrong")
        self.assertEqual(wrong_password.exception.code, AuthenticationFailureCode.INVALID_PASSWORD)

        with self.assertRaises(AuthenticationFailed) as missing_user:
            authenticate_user(db=self.db, username="nobody", password="secret123")
        self.assertEqual(missing_user.exception.code, AuthenticationFailureCode.USER_NOT_FOUND)

    def test_change_user_password_updates_credentials(self):
        user = create_user(db=self.db, username="alice", password="secret123")
        old_hash = user.password_hash

        updated = change_user_password(
            db=self.db,
            user=user,
            current_password="secret123",
            new_password="better-secret123",
        )

        self.assertEqual(updated.id, user.id)
        self.assertNotEqual(updated.password_hash, old_hash)
        authenticated = authenticate_user(db=self.db, username="alice", password="better-secret123")
        self.assertEqual(authenticated.id, user.id)

        with self.assertRaises(AuthenticationFailed) as old_password:
            authenticate_user(db=self.db, username="alice", password="secret123")
        self.assertEqual(old_password.exception.code, AuthenticationFailureCode.INVALID_PASSWORD)

    def test_change_user_password_rejects_invalid_current_password(self):
        user = create_user(db=self.db, username="alice", password="secret123")

        with self.assertRaises(PasswordChangeFailed) as wrong_password:
            change_user_password(
                db=self.db,
                user=user,
                current_password="wrong",
                new_password="better-secret123",
            )
        self.assertEqual(
            wrong_password.exception.code,
            PasswordChangeFailureCode.INVALID_CURRENT_PASSWORD,
        )
        authenticated = authenticate_user(db=self.db, username="alice", password="secret123")
        self.assertEqual(authenticated.id, user.id)

    def test_change_user_password_rejects_unchanged_password(self):
        user = create_user(db=self.db, username="alice", password="secret123")

        with self.assertRaises(PasswordChangeFailed) as unchanged_password:
            change_user_password(
                db=self.db,
                user=user,
                current_password="secret123",
                new_password="secret123",
            )
        self.assertEqual(
            unchanged_password.exception.code,
            PasswordChangeFailureCode.PASSWORD_UNCHANGED,
        )

    def test_session_cookie_roundtrip(self):
        user = create_user(db=self.db, username="bob", password="secret123")
        token = create_user_session(db=self.db, user=user)
        request = SimpleNamespace(cookies={"chatchat_session": token})
        before_last_seen = self.db.query(UserSession).first().last_seen_at

        resolved = resolve_request_user(db=self.db, request=request)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.id, user.id)
        after_last_seen = self.db.query(UserSession).first().last_seen_at
        self.assertEqual(after_last_seen, before_last_seen)

        invalidate_user_session(db=self.db, token=token)
        resolved_after_logout = resolve_request_user(db=self.db, request=request)
        self.assertIsNone(resolved_after_logout)

    def test_apply_session_cookie_sets_http_only_cookie(self):
        response = Response()
        apply_session_cookie(response, "token-value")

        raw_cookie = response.headers.get("set-cookie", "")
        self.assertIn("HttpOnly", raw_cookie)
        self.assertIn("chatchat_session=token-value", raw_cookie)


if __name__ == "__main__":
    unittest.main()

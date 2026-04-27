from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..storage.database import get_db
from ..storage.models import User, UserSession
from .security import generate_session_token, hash_password, session_token_hash, verify_password


class AuthenticationFailureCode(str, Enum):
    USER_NOT_FOUND = "user_not_found"
    INVALID_PASSWORD = "invalid_password"


class PasswordChangeFailureCode(str, Enum):
    INVALID_CURRENT_PASSWORD = "invalid_current_password"
    PASSWORD_UNCHANGED = "password_unchanged"


class AuthenticationFailed(Exception):
    def __init__(self, code: AuthenticationFailureCode):
        self.code = code
        super().__init__(code.value)


class PasswordChangeFailed(Exception):
    def __init__(self, code: PasswordChangeFailureCode):
        self.code = code
        super().__init__(code.value)


def normalize_username(value: str) -> str:
    return value.strip()


def get_user_by_username(db: Session, username: str) -> User | None:
    normalized = normalize_username(username)
    if not normalized:
        return None
    return db.scalar(select(User).where(User.username == normalized))


def create_user(*, db: Session, username: str, password: str, is_active: bool = True) -> User:
    normalized = normalize_username(username)
    if not normalized:
        raise ValueError("Username cannot be empty.")
    if get_user_by_username(db, normalized) is not None:
        raise ValueError("Username already exists.")

    user = User(
        username=normalized,
        password_hash=hash_password(password),
        is_active=bool(is_active),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_user_password(*, db: Session, user: User, password: str) -> User:
    user.password_hash = hash_password(password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def change_user_password(*, db: Session, user: User, current_password: str, new_password: str) -> User:
    if not verify_password(current_password, user.password_hash):
        raise PasswordChangeFailed(PasswordChangeFailureCode.INVALID_CURRENT_PASSWORD)
    if verify_password(new_password, user.password_hash):
        raise PasswordChangeFailed(PasswordChangeFailureCode.PASSWORD_UNCHANGED)
    return set_user_password(db=db, user=user, password=new_password)


def authenticate_user(*, db: Session, username: str, password: str) -> User:
    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        raise AuthenticationFailed(AuthenticationFailureCode.USER_NOT_FOUND)
    if not verify_password(password, user.password_hash):
        raise AuthenticationFailed(AuthenticationFailureCode.INVALID_PASSWORD)
    return user


def create_user_session(*, db: Session, user: User) -> str:
    token = generate_session_token()
    now = datetime.utcnow()
    session = UserSession(
        user_id=user.id,
        token_hash=session_token_hash(token),
        expires_at=now + timedelta(hours=max(1, settings.auth_session_ttl_hours)),
        last_seen_at=now,
    )
    db.add(session)
    db.commit()
    return token


def invalidate_user_session(*, db: Session, token: str | None) -> None:
    raw_token = (token or "").strip()
    if not raw_token:
        return
    db.execute(delete(UserSession).where(UserSession.token_hash == session_token_hash(raw_token)))
    db.commit()


def session_cookie_max_age_seconds() -> int:
    return max(1, settings.auth_session_ttl_hours) * 60 * 60


def apply_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=token,
        httponly=True,
        max_age=session_cookie_max_age_seconds(),
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_session_cookie_name,
        path="/",
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )


def resolve_request_user(*, db: Session, request: Request) -> User | None:
    token = (request.cookies.get(settings.auth_session_cookie_name) or "").strip()
    if not token:
        return None

    now = datetime.utcnow()
    session = db.scalar(
        select(UserSession)
        .join(User)
        .where(
            UserSession.token_hash == session_token_hash(token),
            UserSession.expires_at > now,
            User.is_active.is_(True),
        )
    )
    if session is None:
        return None

    return session.user


def require_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    user = resolve_request_user(db=db, request=request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from ..auth import (
    AuthenticationFailed,
    AuthenticationFailureCode,
    apply_session_cookie,
    authenticate_user,
    clear_session_cookie,
    create_user_session,
    invalidate_user_session,
    require_current_user,
)
from ..core.config import settings
from ..schemas import LoginRequest, SessionOut, UserOut
from ..storage.database import get_db
from ..storage.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=SessionOut)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    try:
        user = authenticate_user(
            db=db,
            username=payload.username,
            password=payload.password,
        )
    except AuthenticationFailed as exc:
        if exc.code is AuthenticationFailureCode.USER_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": exc.code.value,
                    "message": "用户未注册",
                },
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": exc.code.value,
                "message": "密码错误",
            },
        ) from exc

    token = create_user_session(db=db, user=user)
    apply_session_cookie(response, token)
    return SessionOut(user=UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    invalidate_user_session(
        db=db,
        token=request.cookies.get(settings.auth_session_cookie_name),
    )
    clear_session_cookie(response)


@router.get("/session", response_model=SessionOut)
def get_session(current_user: User = Depends(require_current_user)):
    return SessionOut(user=UserOut.model_validate(current_user))

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import client_ip, current_user, enforce_limit
from app.auth import authenticate, create_session, hash_password, revoke_session, verify_password
from app.config import COOKIE_SECURE, LOGIN_ATTEMPTS_PER_15_MIN, SESSION_COOKIE, SESSION_DAYS
from app.db import get_db
from app.models import User
from app.schemas import DeleteAccountRequest, LoginRequest, RegisterRequest, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

TOO_MANY = "Too many attempts. Please wait a few minutes and try again."


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=COOKIE_SECURE, httponly=True, samesite="lax")


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, created_at=user.created_at)


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce_limit(f"register:{client_ip(request)}", 10, 3600, TOO_MANY)

    if db.scalar(select(User.id).where(User.email == body.email)):
        raise HTTPException(409, "An account with this email already exists.")
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # lost a race with a concurrent signup
        db.rollback()
        raise HTTPException(409, "An account with this email already exists.") from None

    _set_session_cookie(response, create_session(db, user))
    return _user_out(user)


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce_limit(f"login-ip:{client_ip(request)}", LOGIN_ATTEMPTS_PER_15_MIN * 3, 900, TOO_MANY)
    enforce_limit(f"login-email:{body.email}", LOGIN_ATTEMPTS_PER_15_MIN, 900, TOO_MANY)

    user = authenticate(db, body.email, body.password)
    if user is None:
        raise HTTPException(401, "Incorrect email or password.")
    _set_session_cookie(response, create_session(db, user))
    return _user_out(user)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    if token:
        revoke_session(db, token)
    _clear_session_cookie(response)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return _user_out(user)


@router.delete("/me", status_code=204)
def delete_account(
    body: DeleteAccountRequest,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Permanently delete the account, its sessions and all saved routines."""
    enforce_limit(f"delete:{user.id}", LOGIN_ATTEMPTS_PER_15_MIN, 900, TOO_MANY)
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(401, "Incorrect password.")
    db.delete(user)
    db.commit()
    _clear_session_cookie(response)

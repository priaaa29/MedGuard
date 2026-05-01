from functools import lru_cache

from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy.orm import Session, sessionmaker

from app.auth import user_for_token
from app.config import LLM_PROVIDER, SESSION_COOKIE
from app.db import SessionLocal, get_db
from app.llm.client import ClaudeLLM, StructuredLLM
from app.models import User
from app.ratelimit import limiter


@lru_cache(maxsize=1)
def get_llm() -> StructuredLLM:
    if LLM_PROVIDER == "anthropic":
        return ClaudeLLM()
    from app.llm.gemini import GeminiLLM

    return GeminiLLM()


def get_session_factory() -> sessionmaker:
    """Session factory for background jobs, which outlive the request's session."""
    return SessionLocal


def current_user(
    db: Session = Depends(get_db),
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> User:
    user = user_for_token(db, token) if token else None
    if user is None:
        raise HTTPException(401, "Please log in.")
    return user


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_limit(key: str, limit: int, window_seconds: int, message: str) -> None:
    if not limiter.hit(key, limit, window_seconds):
        raise HTTPException(429, message)

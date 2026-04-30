"""Passwords and server-side sessions.

The browser holds a random token in an httpOnly cookie; the database holds only
its SHA-256, so a leaked database can't be used to log in, and deleting the row
logs the session out everywhere.
"""

import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import SESSION_DAYS
from app.db import utcnow
from app.models import AuthSession, User

_hasher = PasswordHasher()
# Verified against when the email doesn't exist, so a login for an unknown
# account takes as long as one with a wrong password.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_password(_DUMMY_HASH, password)
        return None
    if not verify_password(user.password_hash, password):
        return None
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.commit()
    return user


def create_session(db: Session, user: User) -> str:
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= utcnow()))
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=_token_hash(token),
            expires_at=utcnow() + timedelta(days=SESSION_DAYS),
        )
    )
    db.commit()
    return token


def user_for_token(db: Session, token: str) -> User | None:
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == _token_hash(token),
            AuthSession.expires_at > utcnow(),
        )
    )
    return session.user if session else None


def revoke_session(db: Session, token: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
    db.commit()

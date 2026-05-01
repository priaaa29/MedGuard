import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow


def new_id() -> str:
    # Random, non-sequential ids so records can't be enumerated.
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    routines: Mapped[list["SavedRoutine"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # SHA-256 of the cookie token; the token itself is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class SavedRoutine(Base):
    __tablename__ = "routines"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    # Confirmed inputs and the full result, as JSON (schemas.AnalyzeRequest / AnalysisResult).
    medications: Mapped[list] = mapped_column(JSON)
    schedule: Mapped[dict] = mapped_column(JSON)
    # Built in the background: pending -> ready | failed.
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="routines")

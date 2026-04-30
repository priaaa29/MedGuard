from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """Naive UTC. SQLite drops timezone info, so store everything naive-UTC."""
    return datetime.now(UTC).replace(tzinfo=None)


def make_engine(url: str) -> Engine:
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        # SQLite ignores foreign keys (and so ON DELETE CASCADE) unless asked.
        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    return engine


engine = make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db(bind: Engine = engine) -> None:
    from app import models  # noqa: F401  (registers tables)

    Base.metadata.create_all(bind)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session

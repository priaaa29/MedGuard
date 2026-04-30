from datetime import time

import pytest

from app.llm.client import LLMError
from app.schemas import DailySchedule


class FakeLLM:
    """Returns queued responses per output model; records every call."""

    def __init__(self, responses=None):
        self.responses = {k: list(v) for k, v in (responses or {}).items()}
        self.calls = []

    def parse(self, *, system, content, output_model, effort=None):
        self.calls.append({"system": system, "content": content, "output_model": output_model})
        queue = self.responses.get(output_model)
        if not queue:
            raise LLMError(f"No fake response for {output_model.__name__}")
        response = queue.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def schedule():
    return DailySchedule(
        wake=time(7, 0),
        breakfast=time(8, 0),
        lunch=time(13, 0),
        dinner=time(20, 0),
        sleep=time(23, 0),
    )


@pytest.fixture
def make_client(tmp_path):
    """Factory for TestClients backed by a fresh SQLite file and a fake LLM."""
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.api.deps import get_llm
    from app.db import get_db, init_db, make_engine
    from app.main import app
    from app.ratelimit import limiter

    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with session_factory() as session:
            yield session

    limiter.reset()
    state = {"llm": FakeLLM()}
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_llm] = lambda: state["llm"]

    def factory(llm=None):
        if llm is not None:
            state["llm"] = llm
        return TestClient(app)

    factory.session = session_factory
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()

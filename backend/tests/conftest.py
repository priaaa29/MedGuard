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

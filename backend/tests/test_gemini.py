import base64
from types import SimpleNamespace

import pytest
from google.genai import errors, types

from app.llm.client import NOT_CONFIGURED, LLMError
from app.llm.gemini import GeminiLLM, to_parts
from app.schemas import RoutineDraft

DRAFT_JSON = '{"doses": [{"medicine": "A", "time": "08:00", "note": "With breakfast"}], "food_guidance": [], "summary": "s"}'


def response(parsed=None, text=DRAFT_JSON, finish="STOP", block_reason=None):
    return SimpleNamespace(
        parsed=parsed,
        text=text,
        candidates=[SimpleNamespace(finish_reason=types.FinishReason[finish])],
        prompt_feedback=SimpleNamespace(block_reason=block_reason) if block_reason else None,
        usage_metadata=SimpleNamespace(prompt_token_count=10, candidates_token_count=5),
    )


class FakeModels:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def llm_with(outcome):
    models = FakeModels(outcome)
    return GeminiLLM(model="test-model", api_key="k", client=SimpleNamespace(models=models)), models


def call(llm, content=None):
    return llm.parse(
        system="sys", content=content or [{"type": "text", "text": "hi"}], output_model=RoutineDraft
    )


def test_converts_text_image_and_pdf_blocks():
    png = b"\x89PNG\r\n\x1a\nxyz"
    parts = to_parts(
        [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                         "data": base64.standard_b64encode(png).decode()}},
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                            "data": base64.standard_b64encode(b"%PDF-1").decode()}},
            {"type": "text", "text": "Transcribe"},
        ]
    )
    assert parts[0].inline_data.data == png and parts[0].inline_data.mime_type == "image/png"
    assert parts[1].inline_data.mime_type == "application/pdf"
    assert parts[2].text == "Transcribe"


def test_request_uses_schema_and_system_prompt():
    llm, models = llm_with(response(parsed=RoutineDraft.model_validate_json(DRAFT_JSON)))
    result = call(llm)
    assert isinstance(result, RoutineDraft) and result.doses[0].time == "08:00"
    config = models.calls[0]["config"]
    assert models.calls[0]["model"] == "test-model"
    assert config.response_schema is RoutineDraft and config.response_mime_type == "application/json"
    assert config.system_instruction == "sys"


def test_falls_back_to_parsing_text():
    llm, _ = llm_with(response(parsed=None))
    assert call(llm).summary == "s"


def test_unreadable_response():
    llm, _ = llm_with(response(parsed=None, text="not json"))
    with pytest.raises(LLMError, match="unreadable"):
        call(llm)


@pytest.mark.parametrize("finish", ["SAFETY", "PROHIBITED_CONTENT", "SPII"])
def test_safety_stop_is_declined(finish):
    llm, _ = llm_with(response(finish=finish))
    with pytest.raises(LLMError, match="declined"):
        call(llm)


def test_blocked_prompt_is_declined():
    llm, _ = llm_with(response(block_reason="SAFETY"))
    with pytest.raises(LLMError, match="declined"):
        call(llm)


def test_max_tokens():
    llm, _ = llm_with(response(finish="MAX_TOKENS"))
    with pytest.raises(LLMError, match="too long"):
        call(llm)


@pytest.mark.parametrize(
    "error, message",
    [
        (errors.ClientError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}}), "usage limit"),
        (errors.ClientError(403, {"error": {"message": "denied", "status": "PERMISSION_DENIED"}}), "not configured"),
        (errors.ClientError(400, {"error": {"message": "bad", "status": "INVALID_ARGUMENT"}}), "could not process"),
        (errors.ServerError(503, {"error": {"message": "down", "status": "UNAVAILABLE"}}), "had a problem"),
        (ConnectionError("dns"), "Could not reach"),
    ],
)
def test_errors_map_to_user_safe_messages(error, message):
    llm, _ = llm_with(error)
    with pytest.raises(LLMError, match=message):
        call(llm)


def test_missing_key_is_not_configured():
    with pytest.raises(LLMError) as exc:
        call(GeminiLLM(api_key=None))
    assert str(exc.value) == NOT_CONFIGURED

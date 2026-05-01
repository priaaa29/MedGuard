"""Google Gemini implementation of StructuredLLM.

Callers build Anthropic-style content blocks (text / image / document); this
adapter converts them to Gemini parts so the rest of the app stays provider-neutral.
"""

import base64
import logging

from pydantic import BaseModel, ValidationError

from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.llm.client import NOT_CONFIGURED, LLMError

logger = logging.getLogger(__name__)


def _network_errors() -> tuple[type[BaseException], ...]:
    # google-genai talks HTTP through httpx (or httpx2), whose transport errors are not OSErrors.
    found: list[type[BaseException]] = [OSError, TimeoutError]
    for module in ("httpx", "httpx2"):
        try:
            found.append(__import__(module).HTTPError)
        except (ImportError, AttributeError):
            pass
    return tuple(found)


_NETWORK_ERRORS = _network_errors()

MAX_OUTPUT_TOKENS = 16000
REQUEST_TIMEOUT_MS = 180_000

# Finish reasons that mean the model declined or was stopped by a safety filter.
DECLINED = {
    "SAFETY",
    "RECITATION",
    "BLOCKLIST",
    "PROHIBITED_CONTENT",
    "SPII",
    "IMAGE_SAFETY",
    "IMAGE_PROHIBITED_CONTENT",
}


def to_parts(content: list[dict]):
    from google.genai import types

    parts = []
    for block in content:
        kind = block.get("type")
        if kind == "text":
            parts.append(types.Part.from_text(text=block["text"]))
        elif kind in ("image", "document"):
            source = block["source"]
            parts.append(
                types.Part.from_bytes(
                    data=base64.standard_b64decode(source["data"]), mime_type=source["media_type"]
                )
            )
        else:
            raise ValueError(f"Unsupported content block: {kind}")
    return parts


class GeminiLLM:
    def __init__(self, model: str = GEMINI_MODEL, api_key: str | None = GEMINI_API_KEY, client=None):
        self.model = model
        self._api_key = api_key
        self._client = client

    @property
    def client(self):
        # Created lazily so the API starts (and tests run) without a key.
        if self._client is None:
            if not self._api_key:
                raise LLMError(NOT_CONFIGURED)
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self._api_key, http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS)
            )
        return self._client

    def parse(self, *, system, content, output_model: type[BaseModel], effort=None):
        from google.genai import errors, types

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[types.Content(role="user", parts=to_parts(content))],
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=output_model,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                ),
            )
        except errors.ClientError as exc:
            logger.error("Gemini client error %s: %s", exc.code, exc.message)
            if exc.code == 429:
                raise LLMError(
                    "The AI service has reached its usage limit for now. Please try again later."
                ) from exc
            if exc.code in (401, 403):
                raise LLMError(NOT_CONFIGURED) from exc
            raise LLMError("The AI service could not process this input.") from exc
        except errors.ServerError as exc:
            logger.error("Gemini server error %s: %s", exc.code, exc.message)
            raise LLMError("The AI service had a problem. Please try again.") from exc
        except errors.APIError as exc:
            logger.error("Gemini API error: %s", exc)
            raise LLMError("The AI service had a problem. Please try again.") from exc
        except LLMError:
            raise
        except _NETWORK_ERRORS as exc:  # connection / DNS / timeout
            raise LLMError("Could not reach the AI service. Please try again.") from exc

        usage = response.usage_metadata
        candidate = (response.candidates or [None])[0]
        finish = getattr(getattr(candidate, "finish_reason", None), "name", None)
        logger.info(
            "gemini call model=%s finish=%s in=%s out=%s",
            self.model,
            finish,
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "candidates_token_count", None),
        )

        if response.prompt_feedback and response.prompt_feedback.block_reason:
            raise LLMError("The AI service declined to process this input.")
        if finish in DECLINED:
            raise LLMError("The AI service declined to process this input.")
        if finish == "MAX_TOKENS":
            raise LLMError("The AI response was too long. Try fewer medicines at once.")

        parsed = response.parsed
        if isinstance(parsed, output_model):
            return parsed
        try:
            return output_model.model_validate_json(response.text or "")
        except (ValidationError, ValueError) as exc:
            raise LLMError("The AI service returned an unreadable response.") from exc

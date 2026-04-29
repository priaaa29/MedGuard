"""Thin wrapper around the Anthropic SDK for structured (Pydantic) outputs.

Everything model-related goes through `StructuredLLM.parse`, so tests can swap
in a fake and the rest of the app never touches the SDK directly.
"""

import logging
from typing import Protocol, TypeVar

import anthropic
from pydantic import BaseModel

from app.config import CLAUDE_EFFORT, CLAUDE_MODEL

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

MAX_TOKENS = 16000
REQUEST_TIMEOUT_SECONDS = 180
NOT_CONFIGURED = "The AI service is not configured (missing or invalid API key)."


class LLMError(RuntimeError):
    """The model call failed or returned nothing usable. Message is user-safe."""


class StructuredLLM(Protocol):
    def parse(
        self,
        *,
        system: str,
        content: list[dict],
        output_model: type[T],
        effort: str | None = None,
    ) -> T: ...


class ClaudeLLM:
    def __init__(self, model: str = CLAUDE_MODEL, effort: str = CLAUDE_EFFORT):
        self.model = model
        self.effort = effort
        self._client: anthropic.Anthropic | None = None

    @property
    def client(self) -> anthropic.Anthropic:
        # Created lazily so the API can start (and tests can run) without credentials.
        if self._client is None:
            self._client = anthropic.Anthropic(max_retries=3, timeout=REQUEST_TIMEOUT_SECONDS)
        return self._client

    def parse(self, *, system, content, output_model, effort=None):
        try:
            response = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": content}],
                output_format=output_model,
                output_config={"effort": effort or self.effort},
                # If a safety classifier declines (false positives happen on medical
                # text), retry server-side on Anthropic's recommended fallback model.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as exc:
            raise LLMError(NOT_CONFIGURED) from exc
        except TypeError as exc:
            # The SDK raises TypeError (not AuthenticationError) when no credentials exist.
            if "authentication method" in str(exc):
                raise LLMError(NOT_CONFIGURED) from exc
            raise
        except anthropic.RateLimitError as exc:
            raise LLMError("The AI service is busy. Please try again in a minute.") from exc
        except anthropic.BadRequestError as exc:
            logger.error("Claude rejected the request: %s", exc)
            raise LLMError("The AI service could not process this input.") from exc
        except anthropic.APIStatusError as exc:
            logger.error("Claude API error %s: %s", exc.status_code, exc)
            raise LLMError("The AI service had a problem. Please try again.") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Could not reach the AI service. Please try again.") from exc

        logger.info(
            "claude call model=%s request_id=%s stop=%s in=%s out=%s",
            response.model,
            response._request_id,
            response.stop_reason,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        if response.stop_reason == "refusal":
            raise LLMError("The AI service declined to process this input.")
        if response.stop_reason == "max_tokens":
            raise LLMError("The AI response was too long. Try fewer medicines at once.")

        parsed = response.parsed_output
        if parsed is None:
            raise LLMError("The AI service returned an unreadable response.")
        return parsed

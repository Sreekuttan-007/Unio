"""The language model behind a small interface, so Gemini can be swapped or switched off.

A provider only ever sees text and returns a validated structure. It has no tools and cannot touch
the database. Any failure returns None, and the caller falls back to rules.
"""

import asyncio
import logging
from typing import Protocol, TypeVar

from pydantic import BaseModel

log = logging.getLogger("unio.llm")
T = TypeVar("T", bound=BaseModel)


class LlmProvider(Protocol):
    name: str

    async def complete_json(self, *, instruction: str, content: str, schema: type[T]) -> T | None: ...


class DisabledProvider:
    name = "disabled"

    async def complete_json(self, *, instruction: str, content: str, schema: type[T]) -> T | None:
        return None


class GeminiProvider:
    """Uses the google-genai Interactions API with a JSON schema, as Google documents it.

    Google ignores some schema keywords such as maxLength, so the caller validates the result again.
    This has not been run against the live API in this repository's tests, which use a fake provider.
    """

    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._timeout = timeout_seconds

    def _call(self, prompt: str, schema: type[T]) -> T:
        interaction = self._client.interactions.create(
            model=self._model,
            input=prompt,
            response_format={"type": "text", "mime_type": "application/json", "schema": schema.model_json_schema()},
        )
        return schema.model_validate_json(interaction.output_text)

    async def complete_json(self, *, instruction: str, content: str, schema: type[T]) -> T | None:
        prompt = f"{instruction}\n\n<data>\n{content}\n</data>"
        try:
            return await asyncio.wait_for(asyncio.to_thread(self._call, prompt, schema), timeout=self._timeout)
        except Exception as error:  # noqa: BLE001 - any failure means "use the fallback"
            log.warning("Gemini call failed: %s", type(error).__name__)
            return None


def build_provider(name: str, api_key: str, model: str, timeout_seconds: float) -> LlmProvider:
    if name == "gemini" and api_key:
        return GeminiProvider(api_key, model, timeout_seconds)
    return DisabledProvider()

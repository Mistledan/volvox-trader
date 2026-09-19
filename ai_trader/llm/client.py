"""Provider-agnostic LLM client built on LiteLLM.

LiteLLM lets one interface route to OpenAI, Anthropic, Gemini, Groq,
Ollama, or any OpenAI-compatible endpoint by changing config only.
"""
from __future__ import annotations

import json
from typing import Any

from dotenv import load_dotenv
from litellm import completion

from ..config import PROJECT_ROOT, LLMConfig
from ..utils.logging import get_logger

log = get_logger("ai_trader.llm")


class LLMError(RuntimeError):
    pass


class LLMClient:
    """Minimal async-anticipating wrapper; sync calls are fine for this workload."""

    def __init__(self, cfg: LLMConfig) -> None:
        load_dotenv(PROJECT_ROOT / ".env")
        self.cfg = cfg
        self.model = cfg.model
        self.temperature = cfg.temperature
        self.max_tokens = cfg.max_tokens

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send a completion request and return the text response."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
        }
        try:
            resp = completion(**kwargs)
            content = resp.choices[0].message.content or ""
            log.debug("llm.response(%d chars)", len(content))
            return content
        except Exception as exc:  # noqa: BLE001 - surface provider errors rowwly
            log.error("LLM call failed: %s", exc)
            raise LLMError(str(exc)) from exc

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Request a JSON object; extract from possible markdown fences."""
        raw = self.complete(system_prompt, user_prompt, temperature=temperature)
        return _extract_json(raw)


def _extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        obj = json.loads(text)
        if not isinstance(obj, dict):
            raise LLMError(f"Expected JSON object, got {type(obj).__name__}")
        return obj
    except json.JSONDecodeError:
        # fallback: locate the first balanced {...} block
        start, end = _find_json_span(text)
        if start == -1:
            raise LLMError(f"Could not parse JSON from LLM output: {raw[:300]!r}")
        try:
            obj = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"Malformed JSON in LLM output: {exc}") from exc
        if not isinstance(obj, dict):
            raise LLMError("LLM JSON output is not a dict")
        return obj


def _find_json_span(text: str) -> tuple[int, int]:
    start = text.find("{")
    if start == -1:
        return -1, -1
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return start, i
    return start, -1
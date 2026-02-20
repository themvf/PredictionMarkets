"""GPT-4o wrapper with retry logic and JSON coercion.

Follows the LLMClient pattern from codex_agent/llm.py:
- Retry loop (3 attempts)
- JSON coercion (strip markdown fences)
- Error handling with descriptive messages
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from config import OpenAIConfig


class OpenAIClientError(RuntimeError):
    """Raised when OpenAI interaction fails."""


class OpenAIClient:
    MAX_RETRIES = 3

    def __init__(self, config: OpenAIConfig) -> None:
        self.config = config
        self._client = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise OpenAIClientError("OpenAI SDK not installed.") from exc

            api_key = self.config.api_key or os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                raise OpenAIClientError("OPENAI_API_KEY is not set.")
            self._client = OpenAI(api_key=api_key)
        return self._client

    def chat(self, prompt: str, system: str = "",
             expect_json: bool = False) -> Dict[str, Any] | str:
        """Send a prompt to GPT-4o with retry logic.

        If expect_json=True, attempts to parse the response as JSON
        with markdown fence stripping.
        """
        last_error: Optional[Exception] = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                raw = self._call(prompt, system)
            except Exception as exc:
                last_error = exc
                continue

            if not expect_json:
                return raw

            try:
                clean = self._coerce_json(raw)
                return json.loads(clean)
            except json.JSONDecodeError as exc:
                last_error = OpenAIClientError(
                    f"GPT-4o returned invalid JSON (attempt {attempt}): {exc}"
                )
                continue

        raise OpenAIClientError(
            f"All {self.MAX_RETRIES} attempts failed. Last error: {last_error}"
        )

    def _call(self, prompt: str, system: str = "") -> str:
        """Make the actual API call to OpenAI."""
        client = self._get_client()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        else:
            messages.append({
                "role": "system",
                "content": "You are a prediction market analyst. Respond precisely and concisely.",
            })
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            messages=messages,
        )
        return response.choices[0].message.content

    @staticmethod
    def _coerce_json(text: str) -> str:
        """Strip markdown fences from LLM JSON output.

        Handles patterns like:
          ```json\n{...}\n```
          ```\n{...}\n```
        """
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped

        parts = stripped.split("```")
        for part in parts:
            candidate = part.strip()
            if not candidate:
                continue
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].lstrip()
            if candidate:
                return candidate
        return stripped

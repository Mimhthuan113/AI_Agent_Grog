"""
Groq Client — LLM API Client voi retry logic
===============================================
Ket noi voi Groq API (free tier) de parse y dinh nguoi dung.

Dac diem:
- Exponential backoff khi gap 429 (rate limit)
- Timeout protection
- Response validation
- Khong lo API key trong log
"""

from __future__ import annotations

import json
import time
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class GroqResponse:
    """Ket qua tu Groq API."""
    content: str
    model: str
    usage_tokens: int
    latency_ms: int
    success: bool
    error: str | None = None


class GroqClient:
    """
    Client giao tiep voi Groq API.
    Ho tro retry voi exponential backoff.
    """

    API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.groq_api_key
        self._model = settings.groq_model_default
        self._max_tokens = settings.groq_max_tokens
        self._temperature = settings.groq_temperature
        self._timeout = settings.groq_timeout
        self._max_retries = 3

    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> GroqResponse:
        """
        Goi Groq API voi retry logic.

        Args:
            messages: List chat messages [{"role": "system", "content": "..."}]
            model: Override model (optional)
            temperature: Override temperature (optional)
            max_tokens: Override max_tokens (optional)

        Returns:
            GroqResponse
        """
        payload = {
            "model": model or self._model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._temperature,
            "max_tokens": max_tokens or self._max_tokens,
        }

        for attempt in range(self._max_retries + 1):
            try:
                start = time.monotonic()
                result = self._call_api(payload)
                latency = int((time.monotonic() - start) * 1000)

                content = result["choices"][0]["message"]["content"]
                usage = result.get("usage", {}).get("total_tokens", 0)

                logger.info(
                    "[GROQ] OK: model=%s tokens=%d latency=%dms",
                    payload["model"], usage, latency,
                )

                return GroqResponse(
                    content=content,
                    model=payload["model"],
                    usage_tokens=usage,
                    latency_ms=latency,
                    success=True,
                )

            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < self._max_retries:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        "[GROQ] Rate limited (429). Retry %d/%d in %ds...",
                        attempt + 1, self._max_retries, wait,
                    )
                    time.sleep(wait)
                    continue
                else:
                    error_body = ""
                    try:
                        error_body = e.read().decode("utf-8")[:200]
                    except Exception:
                        pass
                    logger.error("[GROQ] HTTP %d: %s", e.code, error_body)
                    return GroqResponse(
                        content="",
                        model=payload["model"],
                        usage_tokens=0,
                        latency_ms=0,
                        success=False,
                        error=f"HTTP {e.code}",
                    )

            except Exception as e:
                logger.error("[GROQ] Error: %s", str(e)[:200])
                return GroqResponse(
                    content="",
                    model=payload["model"],
                    usage_tokens=0,
                    latency_ms=0,
                    success=False,
                    error=str(e)[:200],
                )

        return GroqResponse(
            content="",
            model=payload["model"],
            usage_tokens=0,
            latency_ms=0,
            success=False,
            error="Max retries exceeded",
        )

    def _call_api(self, payload: dict) -> dict:
        """Raw API call toi Groq."""
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.API_URL,
            data=data,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": "SmartAIHomeHub/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


# ── Singleton ──────────────────────────────────────────────

_client: GroqClient | None = None


def get_groq_client() -> GroqClient:
    """Tra ve singleton GroqClient."""
    global _client
    if _client is None:
        _client = GroqClient()
    return _client

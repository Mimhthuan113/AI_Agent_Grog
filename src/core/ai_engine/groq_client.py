"""
Groq Client — LLM API Client voi retry logic
===============================================
Ket noi voi Groq API (free tier) de parse y dinh nguoi dung.

Dac diem:
- Exponential backoff khi gap 429 (rate limit)
- Timeout protection
- Response validation
- Khong lo API key trong log
- Langfuse tracing (optional — graceful degradation)
"""

from __future__ import annotations

import json
import time
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import AsyncGenerator

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

        # Langfuse tracing (optional)
        self._langfuse = None
        try:
            if (hasattr(settings, 'langfuse_public_key') and
                    settings.langfuse_public_key):
                from langfuse import Langfuse
                self._langfuse = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host or "https://cloud.langfuse.com",
                )
                logger.info("[GROQ] Langfuse tracing ENABLED")
        except Exception as e:
            logger.info("[GROQ] Langfuse not available: %s", str(e)[:100])

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

                response = GroqResponse(
                    content=content,
                    model=payload["model"],
                    usage_tokens=usage,
                    latency_ms=latency,
                    success=True,
                )

                # Langfuse trace
                self._trace_llm(
                    messages=payload["messages"],
                    response=content,
                    model=payload["model"],
                    tokens=usage,
                    latency_ms=latency,
                )

                return response

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

    def _trace_llm(
        self,
        messages: list[dict],
        response: str,
        model: str,
        tokens: int,
        latency_ms: int,
    ) -> None:
        """Ghi trace vào Langfuse (nếu có). Fail-safe — không ảnh hưởng LLM."""
        if self._langfuse is None:
            return
        try:
            trace = self._langfuse.trace(
                name="groq-chat",
                metadata={"model": model},
            )
            trace.generation(
                name="llm-call",
                model=model,
                input=messages,
                output=response,
                usage={"total_tokens": tokens},
                metadata={"latency_ms": latency_ms},
            )
        except Exception as e:
            logger.debug("[GROQ] Langfuse trace failed: %s", str(e)[:100])

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

    async def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming chat — yield từng chunk text khi LLM trả về.

        Groq SSE format (OpenAI-compatible):
            data: {"choices":[{"delta":{"content":"Xin"}}]}
            data: {"choices":[{"delta":{"content":" chào"}}]}
            data: [DONE]

        Usage:
            async for chunk in groq.chat_stream(messages):
                print(chunk, end="", flush=True)

        Note: nếu LLM lỗi (network, 4xx, 5xx) → generator kết thúc im lặng,
        không raise. Caller có thể kiểm tra `full_response` đã yield bao nhiêu
        chunk để biết đã có response hay chưa, rồi tự fallback.
        """
        import httpx  # Lazy import — chỉ load khi stream

        payload = {
            "model": model or self._model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._temperature,
            "max_tokens": max_tokens or self._max_tokens,
            "stream": True,
        }

        full_response = ""
        start = time.monotonic()

        try:
            # Timeout dài hơn cho stream — cho phép TTFT chậm + body dài
            timeout = httpx.Timeout(
                connect=5.0,
                read=self._timeout,    # idle timeout giữa các chunk
                write=5.0,
                pool=5.0,
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    self.API_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "SmartAIHomeHub/1.0",
                        "Accept": "text/event-stream",
                    },
                ) as resp:
                    if resp.status_code != 200:
                        error_body = (await resp.aread()).decode("utf-8", errors="replace")[:200]
                        logger.error("[GROQ:Stream] HTTP %d: %s", resp.status_code, error_body)
                        return

                    async for line in resp.aiter_lines():
                        # Bỏ qua heartbeat "..." hoặc dòng rỗng
                        if not line:
                            continue
                        if not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if not data_str:
                            continue
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        # Defensive parsing — tránh KeyError nếu format đổi
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content") or ""
                        if content:
                            full_response += content
                            yield content

            latency = int((time.monotonic() - start) * 1000)
            logger.info(
                "[GROQ:Stream] OK: model=%s chars=%d latency=%dms",
                payload["model"], len(full_response), latency,
            )

            # Trace toàn bộ response sau khi xong (Langfuse) — fail-safe
            if full_response:
                self._trace_llm(
                    messages=payload["messages"],
                    response=full_response,
                    model=payload["model"],
                    tokens=0,  # streaming không trả total_tokens
                    latency_ms=latency,
                )

        except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
            logger.warning("[GROQ:Stream] Timeout: %s", str(e)[:120])
        except httpx.HTTPError as e:
            logger.error("[GROQ:Stream] HTTP error: %s", str(e)[:200])
        except Exception as e:  # noqa: BLE001
            logger.error("[GROQ:Stream] Unexpected: %s", str(e)[:200])


# ── Singleton ──────────────────────────────────────────────

_client: GroqClient | None = None


def get_groq_client() -> GroqClient:
    """Tra ve singleton GroqClient."""
    global _client
    if _client is None:
        _client = GroqClient()
    return _client

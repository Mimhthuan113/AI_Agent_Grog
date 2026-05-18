"""
Voice Route — TTS endpoint
============================
Chỉ dùng một giọng duy nhất: Microsoft Edge TTS vi-VN-HoaiMyNeural.
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from collections import OrderedDict

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.middlewares.auth import CurrentUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["Voice"])

EDGE_VOICE = "vi-VN-HoaiMyNeural"
TTS_CACHE_MAX = 64
_tts_cache: OrderedDict[str, tuple[bytes, str, str]] = OrderedDict()


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


def _clean_tts_text(text: str) -> str:
    """Giữ tiếng Việt để đọc, bỏ emoji/ký tự biểu tượng làm Edge trả audio rỗng."""
    normalized = text.replace("…", ".").replace("...", ".")
    chars: list[str] = []
    for char in normalized:
        category = unicodedata.category(char)
        if category.startswith("C"):
            continue
        if category in {"So", "Sk"}:
            chars.append(" ")
            continue
        chars.append(char)
    cleaned = "".join(chars)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([,.!?;:])", r"\1", cleaned)
    return cleaned


def _edge_tts_candidates(text: str) -> list[str]:
    """
    Tạo các phiên bản cùng tiếng Việt để retry với đúng HoaiMy.
    Không đổi provider và không đổi giọng.
    """
    cleaned = _clean_tts_text(text)
    candidates: list[str] = []

    def add(candidate: str) -> None:
        candidate = _clean_tts_text(candidate)
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    lower = cleaned.lower()
    if "giúp gì cho bạn" in lower:
        add("Tôi có thể giúp gì cho bạn?")
    if "bạn cần gì" in lower:
        add("Bạn cần gì?")
    add(cleaned)
    if not candidates:
        add("Tôi có thể giúp gì cho bạn?")
    return candidates


async def _synthesize_edge_once(text: str) -> bytes | None:
    """Gọi Edge TTS một lần với đúng giọng HoaiMy."""
    try:
        import edge_tts
        communicate = edge_tts.Communicate(
            text,
            EDGE_VOICE,
        )
        audio_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])
        data = audio_buffer.getvalue()
        if len(data) > 0:
            logger.info("[TTS] Edge TTS OK (%d bytes)", len(data))
            return data
    except Exception as e:
        logger.warning("[TTS] Edge TTS failed: %s", str(e)[:100])
    return None


async def _try_edge_tts(text: str) -> bytes | None:
    """Thử Edge TTS — chỉ dùng giọng HoaiMy Neural nữ, retry cùng giọng nếu text kén."""
    for idx, candidate in enumerate(_edge_tts_candidates(text), start=1):
        data = await _synthesize_edge_once(candidate)
        if data:
            if idx > 1:
                logger.info("[TTS] Edge retry OK with sanitized candidate #%d", idx)
            return data
        logger.warning("[TTS] Edge returned no audio for candidate #%d: '%s'", idx, candidate[:80])
    return None


def _cache_key(text: str) -> str:
    normalized_text = _clean_tts_text(text)
    return f"{EDGE_VOICE}:{normalized_text}"


def _get_cached_tts(text: str) -> tuple[bytes, str, str] | None:
    key = _cache_key(text)
    cached = _tts_cache.get(key)
    if cached:
        _tts_cache.move_to_end(key)
        logger.info("[TTS] cache hit (%d chars)", len(key))
    return cached


def _set_cached_tts(text: str, audio: bytes, media_type: str, filename: str) -> None:
    key = _cache_key(text)
    if not key or not audio:
        return
    _tts_cache[key] = (audio, media_type, filename)
    _tts_cache.move_to_end(key)
    while len(_tts_cache) > TTS_CACHE_MAX:
        _tts_cache.popitem(last=False)


@router.post(
    "/tts",
    summary="Text-to-Speech",
    description="Chuyển text thành giọng nói nữ Việt Nam.",
)
async def text_to_speech(
    body: TTSRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Text → Audio MP3 giọng nữ Việt.
    Chỉ dùng Edge TTS HoaiMy Neural để giọng luôn nhất quán.
    """
    logger.info("[TTS] user=%s text='%s'", user.user_id, body.text[:50])

    cached = _get_cached_tts(body.text)
    if cached:
        audio_data, media_type, filename = cached
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type=media_type,
            headers={
                "Content-Disposition": f"inline; filename={filename}",
                "Cache-Control": "public, max-age=300",
                "X-TTS-Voice": EDGE_VOICE,
            },
        )

    media_type = "audio/mpeg"
    filename = "aisha.mp3"

    audio_data = await _try_edge_tts(body.text)

    if audio_data is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail=f"TTS không khả dụng cho giọng {EDGE_VOICE}",
        )

    _set_cached_tts(body.text, audio_data, media_type, filename)

    return StreamingResponse(
        io.BytesIO(audio_data),
        media_type=media_type,
        headers={
            "Content-Disposition": f"inline; filename={filename}",
            "Cache-Control": "no-cache",
            "X-TTS-Voice": EDGE_VOICE,
        },
    )

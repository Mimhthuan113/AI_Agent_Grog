"""
Voice Route — TTS endpoint
============================
Ưu tiên: Edge TTS (HoaiMy Neural nữ)
Fallback: gTTS (Google TTS nữ Việt)
"""

from __future__ import annotations

import io
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.middlewares.auth import CurrentUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["Voice"])

EDGE_VOICE = "vi-VN-HoaiMyNeural"


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


async def _try_edge_tts(text: str) -> bytes | None:
    """Thử Edge TTS — giọng HoaiMy Neural nữ."""
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, EDGE_VOICE)
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


def _try_gtts(text: str) -> bytes | None:
    """Fallback: gTTS — giọng nữ Google Việt."""
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang='vi', slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        data = buf.getvalue()
        logger.info("[TTS] gTTS OK (%d bytes)", len(data))
        return data
    except Exception as e:
        logger.warning("[TTS] gTTS failed: %s", str(e)[:100])
    return None


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
    Ưu tiên Edge TTS (HoaiMy Neural), fallback gTTS (Google).
    """
    logger.info("[TTS] user=%s text='%s'", user.user_id, body.text[:50])

    # 1. Thử Edge TTS
    audio_data = await _try_edge_tts(body.text)

    # 2. Fallback gTTS
    if audio_data is None:
        audio_data = _try_gtts(body.text)

    if audio_data is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="TTS không khả dụng")

    return StreamingResponse(
        io.BytesIO(audio_data),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=aisha.mp3",
            "Cache-Control": "no-cache",
        },
    )

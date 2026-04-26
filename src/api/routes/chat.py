"""
Chat Route — Endpoint chinh de giao tiep voi AI
==================================================
User gui cau tieng Viet → AI parse → Security Gateway → Response

Endpoints:
- POST /chat       → Gui lenh dieu khien
- GET  /devices    → Xem danh sach thiet bi
- GET  /audit      → Xem lich su lenh
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import json as _json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.middlewares.auth import CurrentUser, get_current_user
from src.core.ai_engine.agent import process_message, AgentResponse
from src.services.ha_provider.entity_registry import get_all_entities
from src.core.security.audit_logger import get_audit_logger
from src.api.routes.monitor import emit_pipeline_event

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Chat & Control"])


# ── Request / Response Models ──────────────────────────────

class ChatRequest(BaseModel):
    """Request body cho chat."""
    message: str = Field(
        ..., min_length=1, max_length=500,
        description="Cau lenh tieng Viet",
        examples=["Tat den phong ngu", "Bat dieu hoa 25 do"],
    )
    lat: float | None = Field(None, description="Latitude GPS")
    lng: float | None = Field(None, description="Longitude GPS")


class ChatResponse(BaseModel):
    """Response trả về cho user."""
    response: str
    success: bool
    request_id: str
    category: str = "general"          # smart_home, greeting, time_query, general_chat...
    requires_confirmation: bool = False
    command: dict | None = None
    timestamp: str
    pipeline_steps: list[dict] | None = None  # Workflow monitor


class DeviceInfo(BaseModel):
    entity_id: str
    friendly_name: str
    device_type: str


class AuditEntry(BaseModel):
    request_id: str
    entity_id: str
    action: str
    decision: str
    timestamp: str
    user_id: str


# ── Endpoints ──────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Gửi lệnh hoặc hội thoại",
    description="Gửi câu tiếng Việt — AI sẽ điều khiển thiết bị hoặc trả lời hội thoại.",
)
async def chat(
    body: ChatRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Endpoint chính — nhận câu tiếng Việt, xử lý đa năng như Siri.

    Flow:
    1. Siri Brain phân loại intent
    2. Smart home → Security Gateway
    3. Hội thoại → LLM trả lời trực tiếp
    4. Thời gian/chào hỏi → response tức thì
    """
    ip = request.client.host if request.client else ""

    logger.info(
        "[CHAT] user=%s message='%s' ip=%s",
        user.user_id, body.message[:80], ip,
    )

    result: AgentResponse = await process_message(
        user_message=body.message,
        user_id=user.user_id,
        ip_address=ip,
        session_id=user.session_id,
        user_roles=user.roles,
        user_location={"lat": body.lat, "lng": body.lng} if body.lat and body.lng else None,
    )

    # Broadcast event cho Monitor dashboard
    emit_pipeline_event(
        user_id=user.user_id,
        message=body.message[:80],
        category=result.category,
        steps=result.pipeline_steps,
        result=result.message[:120],
        success=result.success,
        request_id=result.request_id,
    )

    return ChatResponse(
        response=result.message,
        success=result.success,
        request_id=result.request_id,
        category=result.category,
        requires_confirmation=result.requires_confirmation,
        command=result.command_executed,
        timestamp=datetime.now(timezone.utc).isoformat(),
        pipeline_steps=result.pipeline_steps,
    )


# ── Streaming endpoint (SSE) ──────────────────────────────

@router.post(
    "/chat/stream",
    summary="Chat với streaming response (SSE)",
    description=(
        "Trả về response dạng Server-Sent Events. "
        "Mỗi event là JSON: {type, data}. "
        "Type: 'meta' (category, request_id), 'chunk' (text chunk), 'done' (kết thúc)."
    ),
)
async def chat_stream(
    body: ChatRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Streaming chat — chỉ stream cho category general_chat.
    Các category khác (smart_home, time, ...) trả response cố định trong 1 chunk.

    Format event:
        data: {"type":"meta","category":"general_chat","request_id":"abc"}\\n\\n
        data: {"type":"chunk","text":"Xin"}\\n\\n
        data: {"type":"chunk","text":" chào"}\\n\\n
        data: {"type":"done","success":true}\\n\\n
    """
    import asyncio

    ip = request.client.host if request.client else ""
    logger.info("[CHAT:Stream] user=%s message='%s'", user.user_id, body.message[:80])

    # Pre-flight: rate-limit + circuit breaker (sync với endpoint /chat)
    from src.core.security.rate_limiter import get_rate_limiter, RateLimitResult
    rl = get_rate_limiter()
    rate_info = await rl.check_rate_limit(user_id=user.user_id)

    request_id = f"stream-{int(datetime.now().timestamp() * 1000)}"

    if rate_info.result != RateLimitResult.ALLOWED:
        async def blocked_gen():
            yield f"data: {_json.dumps({'type': 'meta', 'category': 'rate_limited', 'request_id': request_id}, ensure_ascii=False)}\n\n"
            msg = rate_info.reason or "Quá nhiều yêu cầu. Thử lại sau."
            yield f"data: {_json.dumps({'type': 'chunk', 'text': msg}, ensure_ascii=False)}\n\n"
            yield f"data: {_json.dumps({'type': 'done', 'success': False, 'request_id': request_id, 'rate_limited': True}, ensure_ascii=False)}\n\n"
        return StreamingResponse(
            blocked_gen(),
            media_type="text/event-stream",
            status_code=200,  # SSE phải 200, lỗi báo trong payload
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def event_generator():
        from src.core.ai_engine.siri_brain import (
            classify_intent, IntentCategory,
            SIRI_SYSTEM_PROMPT, _get_memory,
        )
        from src.core.ai_engine.groq_client import get_groq_client
        from src.core.location.geocoder import format_location_context

        # Hint khởi tạo cho proxy: gửi 1 comment ngay → nhiều proxy mới flush header
        yield ": stream-start\n\n"

        # 1. Phân loại intent (nhanh, không gọi LLM)
        category = classify_intent(body.message)
        meta = {
            "type": "meta",
            "category": category.value,
            "request_id": request_id,
        }
        yield f"data: {_json.dumps(meta, ensure_ascii=False)}\n\n"

        # 2. Nếu KHÔNG phải general_chat → fallback non-stream qua process_message
        if category != IntentCategory.GENERAL_CHAT:
            try:
                result = await process_message(
                    user_message=body.message,
                    user_id=user.user_id,
                    ip_address=ip,
                    session_id=user.session_id,
                    user_roles=user.roles,
                    user_location=(
                        {"lat": body.lat, "lng": body.lng}
                        if body.lat is not None and body.lng is not None else None
                    ),
                )
                chunk = {"type": "chunk", "text": result.message}
                yield f"data: {_json.dumps(chunk, ensure_ascii=False)}\n\n"
                done = {
                    "type": "done",
                    "success": result.success,
                    "command": result.command_executed,
                    "requires_confirmation": result.requires_confirmation,
                    "request_id": result.request_id,
                }
                yield f"data: {_json.dumps(done, ensure_ascii=False)}\n\n"
            except Exception as e:  # noqa: BLE001
                logger.error("[CHAT:Stream] non-stream error: %s", str(e)[:200])
                yield f"data: {_json.dumps({'type': 'chunk', 'text': 'Aisha gặp sự cố nhỏ. Thử lại nhé!'}, ensure_ascii=False)}\n\n"
                yield f"data: {_json.dumps({'type': 'done', 'success': False, 'request_id': request_id}, ensure_ascii=False)}\n\n"
            return

        # 3. General chat → stream từ LLM
        # format_location_context là sync I/O (HTTP geocode) → wrap to_thread tránh block event loop
        location_context = None
        if body.lat is not None and body.lng is not None:
            try:
                location_context = await asyncio.to_thread(
                    format_location_context, body.lat, body.lng
                )
            except Exception as e:  # noqa: BLE001
                logger.debug("[CHAT:Stream] geocode skip: %s", str(e)[:80])

        memory = _get_memory(user.user_id)
        memory.add("user", body.message)

        system_prompt = SIRI_SYSTEM_PROMPT
        if location_context:
            system_prompt += (
                f"\n\nTHÔNG TIN VỊ TRÍ HIỆN TẠI:\n{location_context}\n"
                "(Dùng thông tin này khi người dùng hỏi về vị trí, địa điểm, hoặc chỉ đường)"
            )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(memory.get_history())

        groq = get_groq_client()
        full_text = ""
        success = True
        try:
            async for piece in groq.chat_stream(messages, max_tokens=200):
                full_text += piece
                chunk = {"type": "chunk", "text": piece}
                yield f"data: {_json.dumps(chunk, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            # Client disconnect → ngừng êm, không log noise
            logger.info("[CHAT:Stream] client disconnected, request_id=%s", request_id)
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("[CHAT:Stream] LLM error: %s", str(e)[:200])
            success = False
            if not full_text:
                # Chưa có chunk nào → báo lỗi cho user
                err = {"type": "chunk", "text": "Aisha đang gặp sự cố nhỏ. Bạn thử lại nhé!"}
                yield f"data: {_json.dumps(err, ensure_ascii=False)}\n\n"

        # Nếu LLM không yield gì (quota / down) → fallback message
        if not full_text:
            success = False
            fallback = "Aisha chưa nghe rõ. Bạn nói lại nhé!"
            yield f"data: {_json.dumps({'type': 'chunk', 'text': fallback}, ensure_ascii=False)}\n\n"
            full_text = fallback

        memory.add("assistant", full_text)

        done = {"type": "done", "success": success, "request_id": request_id}
        yield f"data: {_json.dumps(done, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Tắt buffer Nginx
            "Connection": "keep-alive",
        },
    )


@router.get(
    "/devices",
    response_model=list[DeviceInfo],
    summary="Danh sach thiet bi",
    description="Xem tat ca thiet bi da dang ky trong he thong.",
)
async def list_devices(
    user: CurrentUser = Depends(get_current_user),
):
    """Tra ve danh sach thiet bi tu Entity Registry."""
    entities = get_all_entities()
    return [DeviceInfo(**e) for e in entities]


@router.get(
    "/audit",
    summary="Lich su lenh",
    description="Xem lich su cac lenh da thuc hien (audit log).",
)
async def get_audit_log(
    user: CurrentUser = Depends(get_current_user),
    limit: int = 20,
    all: bool = False,
):
    """
    Trả về audit log của user hiện tại.
    Owner có thể truyền `?all=true` để xem audit của tất cả users.
    """
    audit = get_audit_logger()
    is_owner = "owner" in user.roles
    target_user = None if (all and is_owner) else user.user_id

    records = await audit.query(user_id=target_user, limit=min(limit, 100))
    return {
        "total": len(records),
        "scope": "all" if (all and is_owner) else "self",
        "records": records,
    }


# ── Confirmation Flow ──────────────────────────────────────

import time as _time
from src.core.security.gateway import get_gateway
from src.core.security.pending_store import get_pending_store

_pending_store = get_pending_store()


class ConfirmRequest(BaseModel):
    """Request body cho xác nhận lệnh."""
    request_id: str = Field(..., description="ID lệnh cần xác nhận")
    confirmed: bool = Field(..., description="True = xác nhận, False = huỷ")


class ConfirmResponse(BaseModel):
    """Response xác nhận lệnh."""
    response: str
    success: bool
    request_id: str
    timestamp: str


async def store_pending_command(request_id: str, command: dict, user_id: str):
    """Lưu lệnh chờ xác nhận (Redis nếu có, in-memory fallback)."""
    await _pending_store.store(request_id, command, user_id)


@router.post(
    "/chat/confirm",
    response_model=ConfirmResponse,
    summary="Xác nhận lệnh nguy hiểm",
    description="Xác nhận hoặc huỷ lệnh WARNING/CRITICAL đang chờ.",
)
async def confirm_command(
    body: ConfirmRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Xác nhận lệnh cần xác nhận (climate, lock...).

    Flow:
    1. POST /chat → requires_confirmation=true + request_id
    2. POST /chat/confirm → confirmed=true → thực thi
    """
    pending = await _pending_store.get(body.request_id)

    if not pending:
        return ConfirmResponse(
            response="Lệnh đã hết hạn hoặc không tồn tại. Vui lòng thử lại.",
            success=False,
            request_id=body.request_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # Kiểm tra ownership
    if pending["user_id"] != user.user_id:
        return ConfirmResponse(
            response="Bạn không có quyền xác nhận lệnh này.",
            success=False,
            request_id=body.request_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # Xoá khỏi pending (đã hết tác dụng sau confirm/cancel)
    await _pending_store.delete(body.request_id)

    if not body.confirmed:
        return ConfirmResponse(
            response="Đã huỷ lệnh.",
            success=True,
            request_id=body.request_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # Thực thi lệnh đã xác nhận
    ip = request.client.host if request.client else ""
    gateway = get_gateway()
    cmd = pending["command"]

    gw_result = await gateway.process_command(
        raw_input=cmd,
        user_id=user.user_id,
        ip_address=ip,
        session_id=user.session_id,
        user_roles=user.roles,
    )

    msg = "Đã thực thi thành công!" if gw_result.success else (gw_result.error_msg or "Lỗi khi thực thi")
    return ConfirmResponse(
        response=msg,
        success=gw_result.success,
        request_id=body.request_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

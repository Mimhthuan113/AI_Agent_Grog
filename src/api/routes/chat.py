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

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
):
    """Tra ve audit log (chi user hien tai)."""
    audit = get_audit_logger()
    records = await audit.query(user_id=user.user_id, limit=min(limit, 100))
    return {
        "total": len(records),
        "records": records,
    }


# ── Confirmation Flow ──────────────────────────────────────

import time as _time
from src.core.security.gateway import get_gateway

# Pending commands store: {request_id: {command, user_id, created_at}}
_pending_commands: dict[str, dict] = {}
_PENDING_TTL = 60  # 60 giây timeout


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


def store_pending_command(request_id: str, command: dict, user_id: str):
    """Lưu lệnh chờ xác nhận."""
    _pending_commands[request_id] = {
        "command": command,
        "user_id": user_id,
        "created_at": _time.time(),
    }
    # Cleanup expired
    now = _time.time()
    expired = [k for k, v in _pending_commands.items() if now - v["created_at"] > _PENDING_TTL]
    for k in expired:
        del _pending_commands[k]


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
    pending = _pending_commands.get(body.request_id)

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

    # Kiểm tra TTL
    if _time.time() - pending["created_at"] > _PENDING_TTL:
        del _pending_commands[body.request_id]
        return ConfirmResponse(
            response="Lệnh đã hết hạn (60 giây). Vui lòng thử lại.",
            success=False,
            request_id=body.request_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # Xoá khỏi pending
    del _pending_commands[body.request_id]

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

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


class ChatResponse(BaseModel):
    """Response tra ve cho user."""
    response: str
    success: bool
    request_id: str
    requires_confirmation: bool = False
    command: dict | None = None
    timestamp: str


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
    summary="Gui lenh dieu khien",
    description="Gui cau tieng Viet de dieu khien thiet bi nha thong minh.",
)
async def chat(
    body: ChatRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Endpoint chinh — nhan cau tieng Viet, tra ket qua.

    Flow:
    1. User gui "Tat den phong ngu"
    2. AI parse intent
    3. Security Gateway validate + execute
    4. Tra response tieng Viet
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
    )

    return ChatResponse(
        response=result.message,
        success=result.success,
        request_id=result.request_id,
        requires_confirmation=result.requires_confirmation,
        command=result.command_executed,
        timestamp=datetime.now(timezone.utc).isoformat(),
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

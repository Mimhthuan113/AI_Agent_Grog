"""
Apps Route — API cho App Actions
===================================
Quản lý và thực thi app actions (mở app, gọi, nhắn, tìm kiếm...).

Endpoints:
- GET  /apps          → Danh sách apps + capabilities
- POST /apps/execute  → Thực thi app action
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.middlewares.auth import CurrentUser, get_current_user
from src.core.app_actions.router import (
    get_all_capabilities,
    execute_app_action,
    parse_app_intent,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/apps", tags=["App Actions"])


class AppActionRequest(BaseModel):
    """Request body cho app action."""
    provider: str = Field(..., description="Tên provider (zalo, phone, youtube...)")
    action: str = Field(..., description="Tên action (open_zalo, call, youtube_search...)")
    params: dict = Field(default_factory=dict, description="Tham số")


class AppActionResponse(BaseModel):
    """Response cho app action."""
    success: bool
    message: str
    intent_uri: str | None = None
    data: dict | None = None
    provider: str = ""
    action: str = ""


@router.get(
    "",
    summary="Danh sách ứng dụng",
    description="Xem tất cả app providers và capabilities.",
)
async def list_apps(user: CurrentUser = Depends(get_current_user)):
    """Trả về danh sách toàn bộ app providers."""
    return get_all_capabilities()


@router.post(
    "/execute",
    response_model=AppActionResponse,
    summary="Thực thi app action",
    description="Gửi lệnh tới app provider. Chỉ owner.",
)
async def execute_action(
    body: AppActionRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Thực thi app action — owner only."""
    if "owner" not in user.roles:
        return AppActionResponse(
            success=False,
            message="Chức năng này chỉ dành cho chủ nhà.",
            provider=body.provider,
            action=body.action,
        )

    result = await execute_app_action(body.provider, body.action, body.params)

    return AppActionResponse(
        success=result.success,
        message=result.message,
        intent_uri=result.intent_uri,
        data=result.data,
        provider=result.provider,
        action=result.action,
    )

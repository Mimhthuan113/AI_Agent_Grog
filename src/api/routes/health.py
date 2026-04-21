"""
Health Route — System health check
====================================
Endpoint đơn giản để kiểm tra hệ thống đang chạy.
Docker health check và monitoring tools dùng endpoint này.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["System"])


@router.get(
    "/health",
    summary="Health Check",
    description="Kiểm tra hệ thống đang hoạt động.",
)
async def health_check():
    """
    Health check endpoint.
    Docker health check gọi endpoint này mỗi 30 giây.
    """
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "smart-ai-home-hub",
        "version": "1.0.0",
    }

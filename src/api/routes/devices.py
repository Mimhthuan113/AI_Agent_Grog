"""
Devices Route — API cho Thiết bị nhà thông minh
=================================================
Endpoints:
- GET  /devices          → Danh sách thiết bị (từ Home Assistant)
- POST /devices/control  → Điều khiển thiết bị
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends

from src.api.middlewares.auth import CurrentUser, get_current_user
from src.services.ha_provider.entity_registry import get_all_entities

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/devices", tags=["Devices"])


@router.get(
    "",
    summary="Danh sách thiết bị",
    description="Trả về danh sách thiết bị từ Home Assistant. Nếu chưa kết nối HA thì trả list rỗng.",
)
async def list_devices(user: CurrentUser = Depends(get_current_user)):
    """Lấy danh sách thiết bị từ Home Assistant."""
    try:
        from src.services.ha_provider.ha_client import get_ha_client
        ha = await get_ha_client()
        states = await ha.get_states()
        devices = []
        for state in (states or []):
            entity_id = state.get("entity_id", "")
            # Lọc các loại thiết bị phổ biến
            domain = entity_id.split(".")[0] if "." in entity_id else ""
            if domain not in ("light", "switch", "lock", "climate", "sensor", "binary_sensor"):
                continue
            device_type_map = {
                "light": "light",
                "switch": "switch",
                "lock": "lock",
                "climate": "climate",
                "sensor": "sensor",
                "binary_sensor": "sensor",
            }
            devices.append({
                "entity_id": entity_id,
                "friendly_name": state.get("attributes", {}).get("friendly_name", entity_id),
                "device_type": device_type_map.get(domain, "default"),
                "state": state.get("state", "unknown"),
                "attributes": state.get("attributes", {}),
            })
        return devices
    except Exception as exc:
        logger.warning("[DEVICES] Không lấy được thiết bị từ HA: %s", str(exc)[:200])
        # Fallback dev/test: dùng registry tĩnh để frontend không trống khi chưa kết nối HA.
        return [
            {
                **entity,
                "state": "unknown",
                "attributes": {},
            }
            for entity in get_all_entities()
        ]


@router.post(
    "/control",
    summary="Điều khiển thiết bị",
    description="Gửi lệnh điều khiển thiết bị qua Home Assistant.",
)
async def control_device(
    body: dict,
    user: CurrentUser = Depends(get_current_user),
):
    """Điều khiển thiết bị (bật/tắt/đặt nhiệt độ...)."""
    entity_id = body.get("entity_id", "")
    service = body.get("service", "")
    service_data = body.get("data", {})

    if not entity_id or not service:
        return {"success": False, "message": "Thiếu entity_id hoặc service."}

    try:
        from src.services.ha_provider.ha_client import get_ha_client
        ha = await get_ha_client()
        domain = entity_id.split(".")[0]
        await ha.call_service(domain, service, {"entity_id": entity_id, **service_data})
        return {"success": True, "message": f"Đã gửi lệnh {service} tới {entity_id}."}
    except Exception as exc:
        logger.error("[DEVICES] Lỗi điều khiển thiết bị: %s", exc)
        return {"success": False, "message": f"Lỗi: {exc}"}

"""
RBAC — Role-Based Access Control
==================================
Phân quyền owner vs guest cho điều khiển thiết bị.

Roles:
  - owner: toàn quyền (tất cả entity + action)
  - guest: chỉ đèn + cảm biến (đọc)

Nguyên tắc:
  - Deny-by-default: role không có trong PERMISSIONS → bị chặn
  - RBAC check TRƯỚC Rule Engine (gateway pipeline)
  - Không thay đổi Rule Engine logic — RBAC là lớp bổ sung
"""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RolePermission:
    """Quyền cho 1 role trên 1 nhóm entity."""
    entity_pattern: str
    allowed_actions: tuple[str, ...]


# ── Permission Definitions ─────────────────────────────────

ROLE_PERMISSIONS: dict[str, list[RolePermission]] = {
    "owner": [
        # Owner có toàn quyền — wildcard
        RolePermission("*", (
            "turn_on", "turn_off", "set_brightness", "set_color",
            "lock", "set_temperature", "set_hvac_mode", "get_state",
        )),
    ],

    "guest": [
        # Guest chỉ được điều khiển đèn
        RolePermission("light.*", ("turn_on", "turn_off", "set_brightness")),
        # Và đọc cảm biến
        RolePermission("sensor.*", ("get_state",)),
        RolePermission("binary_sensor.*", ("get_state",)),
        # Guest KHÔNG được: lock, climate, switch (bếp/quạt)
    ],
}


class RBACError(Exception):
    """Permission denied."""
    def __init__(self, role: str, entity_id: str, action: str):
        self.role = role
        self.entity_id = entity_id
        self.action = action
        super().__init__(
            f"Role '{role}' không có quyền '{action}' trên '{entity_id}'"
        )


def check_permission(
    roles: list[str],
    entity_id: str,
    action: str,
) -> bool:
    """
    Kiểm tra user có quyền thực hiện action trên entity không.

    Args:
        roles: List roles từ JWT (ví dụ: ["owner"] hoặc ["guest"])
        entity_id: Entity ID (ví dụ: "light.phong_ngu")
        action: Action (ví dụ: "turn_on")

    Returns:
        True nếu có quyền.

    Raises:
        RBACError nếu không có quyền.
    """
    entity_id = entity_id.strip().lower()
    action = action.strip().lower()

    for role in roles:
        permissions = ROLE_PERMISSIONS.get(role, [])
        for perm in permissions:
            if fnmatch.fnmatch(entity_id, perm.entity_pattern):
                if action in perm.allowed_actions:
                    logger.info(
                        "[RBAC] ALLOWED: role=%s entity=%s action=%s",
                        role, entity_id, action,
                    )
                    return True

    # Deny-by-default
    primary_role = roles[0] if roles else "unknown"
    logger.warning(
        "[RBAC] DENIED: roles=%s entity=%s action=%s",
        roles, entity_id, action,
    )
    raise RBACError(primary_role, entity_id, action)

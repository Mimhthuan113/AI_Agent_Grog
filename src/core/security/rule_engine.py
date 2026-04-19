"""
Rule Engine — Lớp bảo mật NGOÀI LLM
=====================================
Đây là tầng bảo mật quan trọng nhất trong hệ thống.
LLM KHÔNG THỂ bypass module này.

Nguyên tắc:
- LLM chỉ trả về "intent" (entity_id + action)
- Rule Engine quyết định có thực thi không
- Không có rule = bị chặn (Deny-by-default)
"""

from __future__ import annotations
import fnmatch
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SafetyLevel(str, Enum):
    SAFE     = "safe"      # Thực thi ngay
    WARNING  = "warning"   # Hỏi xác nhận người dùng
    CRITICAL = "critical"  # Chặn hoàn toàn — yêu cầu PIN vật lý


@dataclass(frozen=True)
class ActionRule:
    entity_pattern:       str
    allowed_actions:      tuple[str, ...]
    safety_level:         SafetyLevel
    requires_confirmation: bool = False
    deny_actions:         tuple[str, ...] = ()   # Action bị chặn tuyệt đối


# ================================================================
# ALLOW-LIST — ĐÂY LÀ HARD-CODED, KHÔNG QUA LLM, KHÔNG ĐƯỢC SỬA
# QUA API. Phải sửa trực tiếp code → deploy lại.
# ================================================================
RULES: list[ActionRule] = [
    # ── ĐÈN ──────────────────────────────────────────────────────
    ActionRule(
        entity_pattern  = "light.*",
        allowed_actions = ("turn_on", "turn_off", "set_brightness", "set_color"),
        safety_level    = SafetyLevel.SAFE,
    ),

    # ── QUẠT / ĐIỀU HÒA ──────────────────────────────────────────
    ActionRule(
        entity_pattern  = "switch.fan_*",
        allowed_actions = ("turn_on", "turn_off"),
        safety_level    = SafetyLevel.SAFE,
    ),
    ActionRule(
        entity_pattern  = "climate.*",
        allowed_actions = ("set_temperature", "set_hvac_mode", "turn_off"),
        safety_level    = SafetyLevel.WARNING,
        requires_confirmation = True,
    ),

    # ── BẾP / THIẾT BỊ NHIỆT ─────────────────────────────────────
    ActionRule(
        entity_pattern  = "switch.kitchen*",
        allowed_actions = ("turn_off",),          # Chỉ cho phép TẮT
        deny_actions    = ("turn_on",),            # BẬT bị chặn hoàn toàn
        safety_level    = SafetyLevel.CRITICAL,
        requires_confirmation = True,
    ),

    # ── CỬA / KHÓA ───────────────────────────────────────────────
    ActionRule(
        entity_pattern  = "lock.*",
        allowed_actions = ("lock",),               # Chỉ cho phép KHÓA
        deny_actions    = ("unlock",),             # MỞ KHÓA bị chặn tuyệt đối qua AI
        safety_level    = SafetyLevel.CRITICAL,
    ),

    # ── CẢM BIẾN (chỉ đọc) ───────────────────────────────────────
    ActionRule(
        entity_pattern  = "sensor.*",
        allowed_actions = ("get_state",),
        safety_level    = SafetyLevel.SAFE,
    ),
    ActionRule(
        entity_pattern  = "binary_sensor.*",
        allowed_actions = ("get_state",),
        safety_level    = SafetyLevel.SAFE,
    ),
]


class RuleEngineError(Exception):
    """Base error cho Rule Engine."""


class ActionDeniedError(RuleEngineError):
    """Action bị chặn tuyệt đối."""


class ActionNotPermittedError(RuleEngineError):
    """Action không nằm trong allow-list."""


class NoRuleFoundError(RuleEngineError):
    """Không tìm thấy rule cho entity này — Deny by default."""


def evaluate(entity_id: str, action: str) -> SafetyLevel:
    """
    Đánh giá xem lệnh có được phép thực thi không.

    Args:
        entity_id:  ID của entity trong Home Assistant (ví dụ: "light.phong_ngu")
        action:     Action mà LLM đề xuất (ví dụ: "turn_on")

    Returns:
        SafetyLevel tương ứng nếu được phép.

    Raises:
        ActionDeniedError:      Nếu action nằm trong deny_actions.
        ActionNotPermittedError: Nếu action không nằm trong allowed_actions.
        NoRuleFoundError:       Nếu entity_id không khớp với bất kỳ rule nào.
    """
    entity_id = entity_id.strip().lower()
    action    = action.strip().lower()

    for rule in RULES:
        if fnmatch.fnmatch(entity_id, rule.entity_pattern):
            # Kiểm tra deny_actions trước (tuyệt đối)
            if action in rule.deny_actions:
                logger.warning(
                    "[RULE ENGINE] DENIED: entity=%s action=%s (in deny_actions)",
                    entity_id, action
                )
                raise ActionDeniedError(
                    f"Action '{action}' is permanently denied for '{entity_id}'. "
                    "Physical key required."
                )

            # Kiểm tra allowed_actions
            if action not in rule.allowed_actions:
                logger.warning(
                    "[RULE ENGINE] NOT PERMITTED: entity=%s action=%s",
                    entity_id, action
                )
                raise ActionNotPermittedError(
                    f"Action '{action}' is not in the allow-list for '{entity_id}'."
                )

            logger.info(
                "[RULE ENGINE] APPROVED: entity=%s action=%s level=%s",
                entity_id, action, rule.safety_level
            )
            return rule.safety_level

    # Deny by default — entity không có rule
    logger.error(
        "[RULE ENGINE] NO RULE: entity=%s — access denied by default", entity_id
    )
    raise NoRuleFoundError(
        f"No rule found for entity '{entity_id}'. Denied by default."
    )


def requires_confirmation(entity_id: str, action: str) -> bool:
    """Kiểm tra xem lệnh có cần xác nhận từ người dùng không."""
    entity_id = entity_id.strip().lower()
    for rule in RULES:
        if fnmatch.fnmatch(entity_id, rule.entity_pattern):
            return rule.requires_confirmation
    return False

"""
AI Agent — Orchestrator chính của AI Engine
=============================================
Tích hợp Siri Brain + Security Gateway.

Luồng:
  User input (text/voice tiếng Việt)
    → Siri Brain (phân loại intent)
    → Smart Home? → Intent Parser → Security Gateway
    → General? → LLM trả lời trực tiếp
    → Response (text tiếng Việt) → TTS
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.core.ai_engine.intent_parser import parse_intent
from src.core.ai_engine.siri_brain import (
    process as siri_process,
    IntentCategory,
    SiriResponse,
)
from src.core.security.gateway import get_gateway, GatewayResponse
from src.services.ha_provider.entity_registry import ENTITY_REGISTRY

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Kết quả xử lý từ AI Agent."""
    message: str                     # Tin nhắn trả về cho user (tiếng Việt có dấu)
    success: bool
    request_id: str
    category: str = "general"        # Loại intent: smart_home, greeting, time_query...
    requires_confirmation: bool = False
    command_executed: dict | None = None
    speak: bool = True               # Có nên đọc bằng giọng nói không


# ── Response Templates ─────────────────────────────────────

RESPONSE_TEMPLATES = {
    "success": "Đã {action} {entity} thành công!",
    "success_mock": "Đã {action} {entity} (chế độ test).",
    "denied": "Xin lỗi, tôi không thể thực hiện yêu cầu này. Lý do: {reason}",
    "confirm": "Bạn có chắc muốn {action} {entity} không? (Đây là hành động cần xác nhận)",
    "parse_fail": "Xin lỗi, tôi không hiểu yêu cầu của bạn. Hãy thử lại với câu đơn giản hơn.",
    "error": "Có lỗi xảy ra khi xử lý yêu cầu. Vui lòng thử lại sau.",
}

ACTION_NAMES_VI = {
    "turn_on": "bật",
    "turn_off": "tắt",
    "set_brightness": "chỉnh độ sáng",
    "set_color": "đổi màu",
    "lock": "khóa",
    "unlock": "mở khóa",
    "set_temperature": "đặt nhiệt độ",
    "set_hvac_mode": "chuyển chế độ",
    "get_state": "kiểm tra",
}

DENY_REASONS_VI = {
    "ACTION_DENIED": "Hành động này bị chặn vĩnh viễn vì lý do an toàn",
    "ACTION_NOT_PERMITTED": "Hành động này không được phép cho thiết bị này",
    "NO_RULE_FOUND": "Thiết bị này chưa được cấu hình trong hệ thống",
    "PARAM_VALIDATION_ERROR": "Tham số không hợp lệ",
    "INJECTION_DETECTED": "Phát hiện nội dung không hợp lệ trong yêu cầu",
    "INVALID_ENTITY_FORMAT": "Định dạng thiết bị không hợp lệ",
    "CONFIRMATION_REQUIRED": "Cần xác nhận trước khi thực hiện",
}


def _get_entity_name(entity_id: str) -> str:
    """Lấy tên thân thiện từ entity_id (có dấu tiếng Việt)."""
    for alias, info in ENTITY_REGISTRY.items():
        if info.entity_id == entity_id:
            return info.friendly_name
    parts = entity_id.split(".")
    if len(parts) == 2:
        return parts[1].replace("_", " ")
    return entity_id


async def process_message(
    user_message: str,
    user_id: str,
    ip_address: str = "",
    session_id: str = "",
) -> AgentResponse:
    """
    Xử lý 1 tin nhắn từ user — entry point chính.

    Luồng Siri-like:
    1. Siri Brain phân loại intent
    2. Smart home → Intent Parser → Security Gateway
    3. Khác → Siri Brain trả lời trực tiếp
    """
    logger.info("[AGENT] Processing: '%s' (user=%s)", user_message[:80], user_id)

    # ── Step 1: Siri Brain phân loại ──────────────────────
    siri_result: SiriResponse = await siri_process(user_message, user_id)

    # ── Nếu KHÔNG phải smart home → trả lời trực tiếp ────
    if not siri_result.is_smart_home:
        return AgentResponse(
            message=siri_result.text,
            success=True,
            request_id="siri-direct",
            category=siri_result.category.value,
        )

    # ── Smart Home → Intent Parser + Gateway ──────────────
    intent = parse_intent(user_message)

    if intent is None:
        logger.info("[AGENT] Parse failed for: '%s'", user_message[:80])
        return AgentResponse(
            message=RESPONSE_TEMPLATES["parse_fail"],
            success=False,
            request_id="parse-fail",
            category="smart_home",
        )

    entity_id = intent["entity_id"]
    action = intent["action"]
    params = intent.get("params", {})
    entity_name = _get_entity_name(entity_id)
    action_name = ACTION_NAMES_VI.get(action, action)

    # ── Security Gateway ──────────────────────────────────
    gateway = get_gateway()
    gw_result: GatewayResponse = await gateway.process_command(
        raw_input={
            "entity_id": entity_id,
            "action": action,
            "params": params,
        },
        user_id=user_id,
        ip_address=ip_address,
        session_id=session_id,
    )

    # ── Build response ────────────────────────────────────

    if gw_result.requires_confirmation:
        return AgentResponse(
            message=RESPONSE_TEMPLATES["confirm"].format(
                action=action_name, entity=entity_name
            ),
            success=True,
            request_id=gw_result.request_id,
            category="smart_home",
            requires_confirmation=True,
            command_executed=intent,
        )

    if gw_result.success:
        template = "success"
        if gw_result.ha_result and gw_result.ha_result.get("mock"):
            template = "success_mock"

        return AgentResponse(
            message=RESPONSE_TEMPLATES[template].format(
                action=action_name, entity=entity_name
            ),
            success=True,
            request_id=gw_result.request_id,
            category="smart_home",
            command_executed=intent,
        )

    # Denied
    deny_reason = DENY_REASONS_VI.get(
        gw_result.error_code or "", gw_result.error_msg or "Không rõ lý do"
    )
    return AgentResponse(
        message=RESPONSE_TEMPLATES["denied"].format(reason=deny_reason),
        success=False,
        request_id=gw_result.request_id,
        category="smart_home",
    )

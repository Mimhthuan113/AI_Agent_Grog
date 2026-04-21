"""
AI Agent — Orchestrator chinh cua AI Engine
=============================================
Ket noi Intent Parser voi Security Gateway.

Luong:
  User message (tieng Viet)
    → Intent Parser (LLM + Registry)
    → Security Gateway (Sanitize → Rule → Execute → Audit)
    → Response message (tieng Viet)

Nguyen tac:
- Moi lenh PHAI di qua Security Gateway
- KHONG co duong tat nao bypass Gateway
- Response luon user-friendly (tieng Viet)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.core.ai_engine.intent_parser import parse_intent
from src.core.security.gateway import get_gateway, GatewayResponse

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Ket qua xu ly tu AI Agent."""
    message: str                     # Tin nhan tra ve cho user (tieng Viet)
    success: bool
    request_id: str
    requires_confirmation: bool = False
    command_executed: dict | None = None  # Command da thuc thi (neu co)


# ── Response Templates ─────────────────────────────────────

RESPONSE_TEMPLATES = {
    "success": "Da {action} {entity} thanh cong!",
    "success_mock": "Da {action} {entity} (che do test).",
    "denied": "Xin loi, toi khong the thuc hien yeu cau nay. Ly do: {reason}",
    "confirm": "Ban co chac muon {action} {entity} khong? (Day la hanh dong can xac nhan)",
    "parse_fail": "Xin loi, toi khong hieu yeu cau cua ban. Hay thu lai voi cau don gian hon.",
    "error": "Co loi xay ra khi xu ly yeu cau. Vui long thu lai sau.",
}

ACTION_NAMES_VI = {
    "turn_on": "bat",
    "turn_off": "tat",
    "set_brightness": "chinh do sang",
    "set_color": "doi mau",
    "lock": "khoa",
    "unlock": "mo khoa",
    "set_temperature": "dat nhiet do",
    "set_hvac_mode": "chuyen che do",
    "get_state": "kiem tra",
}

DENY_REASONS_VI = {
    "ACTION_DENIED": "Hanh dong nay bi chan vinh vien vi ly do an toan",
    "ACTION_NOT_PERMITTED": "Hanh dong nay khong duoc phep cho thiet bi nay",
    "NO_RULE_FOUND": "Thiet bi nay chua duoc cau hinh trong he thong",
    "PARAM_VALIDATION_ERROR": "Tham so khong hop le",
    "INJECTION_DETECTED": "Phat hien noi dung khong hop le trong yeu cau",
    "INVALID_ENTITY_FORMAT": "Dinh dang thiet bi khong hop le",
    "CONFIRMATION_REQUIRED": "Can xac nhan truoc khi thuc hien",
}


def _get_entity_name(entity_id: str) -> str:
    """Lay ten than thien tu entity_id."""
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
    Xu ly 1 tin nhan tu user.
    Day la entry point chinh cua AI Engine.

    Args:
        user_message: Cau noi tieng Viet tu user
        user_id: User ID tu JWT
        ip_address: IP client
        session_id: Session ID

    Returns:
        AgentResponse voi tin nhan tieng Viet.
    """
    logger.info("[AGENT] Processing: '%s' (user=%s)", user_message[:80], user_id)

    # ── Step 1: Parse intent ───────────────────────────────
    intent = parse_intent(user_message)

    if intent is None:
        logger.info("[AGENT] Parse failed for: '%s'", user_message[:80])
        return AgentResponse(
            message=RESPONSE_TEMPLATES["parse_fail"],
            success=False,
            request_id="parse-fail",
        )

    entity_id = intent["entity_id"]
    action = intent["action"]
    params = intent.get("params", {})
    entity_name = _get_entity_name(entity_id)
    action_name = ACTION_NAMES_VI.get(action, action)

    # ── Step 2: Send qua Security Gateway ──────────────────
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

    # ── Step 3: Build response ─────────────────────────────

    if gw_result.requires_confirmation:
        return AgentResponse(
            message=RESPONSE_TEMPLATES["confirm"].format(
                action=action_name, entity=entity_name
            ),
            success=True,
            request_id=gw_result.request_id,
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
            command_executed=intent,
        )

    # Denied
    deny_reason = DENY_REASONS_VI.get(
        gw_result.error_code or "", gw_result.error_msg or "Khong ro ly do"
    )
    return AgentResponse(
        message=RESPONSE_TEMPLATES["denied"].format(reason=deny_reason),
        success=False,
        request_id=gw_result.request_id,
    )

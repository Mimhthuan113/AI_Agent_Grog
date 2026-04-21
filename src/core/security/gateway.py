"""
Security Gateway — Orchestrator chinh
=======================================
Day la module QUAN TRONG NHAT trong he thong.
Moi lenh tu AI Engine PHAI di qua Gateway truoc khi den Home Assistant.

Luong xu ly:
  AI Engine
    → [1] Sanitizer (validate + clean)
    → [2] Rule Engine (allow-list check)
    → [3] Execute (goi HA)
    → [4] Audit Logger (ghi log)
    → Response

Nguyen tac:
- KHONG co duong tat (bypass) nao
- Moi buoc deu doc lap — fail o buoc nao thi dung o buoc do
- Audit log LUON duoc ghi — ke ca khi bi reject
- Error messages user-friendly, KHONG lo internal details
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from src.core.security.sanitizer import sanitize, CleanCommand, SanitizerError
from src.core.security.rule_engine import (
    evaluate,
    requires_confirmation,
    SafetyLevel,
    ActionDeniedError,
    ActionNotPermittedError,
    NoRuleFoundError,
)
from src.core.security.audit_logger import AuditRecord, get_audit_logger

logger = logging.getLogger(__name__)


# ── Response Models ────────────────────────────────────────

@dataclass
class GatewayResponse:
    """Ket qua xu ly lenh qua Security Gateway."""
    request_id: str
    success: bool
    decision: str           # APPROVED | DENIED | RATE_LIMITED
    safety_level: str
    error_code: str | None = None
    error_msg: str | None = None
    requires_confirmation: bool = False
    confirmation_token: str | None = None
    ha_result: dict | None = None        # Ket qua tu HA
    ha_response_ms: int | None = None


# ── Error Codes ────────────────────────────────────────────

GATEWAY_ERRORS = {
    "SANITIZER_ERROR": "Du lieu dau vao khong hop le",
    "ACTION_DENIED": "Hanh dong bi chan vinh vien",
    "ACTION_NOT_PERMITTED": "Hanh dong khong duoc phep",
    "NO_RULE_FOUND": "Thiet bi khong co quy tac — bi chan mac dinh",
    "CONFIRMATION_REQUIRED": "Can xac nhan truoc khi thuc hien",
    "EXECUTION_ERROR": "Loi khi thuc thi lenh",
    "INTERNAL_ERROR": "Loi he thong noi bo",
}


# ── Gateway Class ──────────────────────────────────────────

class SecurityGateway:
    """
    Security Gateway — orchestrate toan bo luong bao mat.
    Singleton pattern.
    """

    _instance: SecurityGateway | None = None

    def __new__(cls) -> SecurityGateway:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._audit = get_audit_logger()
        # Phase 2: inject ha_client here
        self._ha_client = None

    def set_ha_client(self, client) -> None:
        """Inject HA client (Phase 2 — khi co ha_client.py)."""
        self._ha_client = client

    async def process_command(
        self,
        raw_input: dict,
        user_id: str,
        ip_address: str = "",
        session_id: str = "",
    ) -> GatewayResponse:
        """
        Xu ly 1 lenh tu AI Engine qua toan bo security pipeline.

        Args:
            raw_input:  Dict tu LLM: {"entity_id": "...", "action": "...", "params": {...}}
            user_id:    User ID tu JWT
            ip_address: IP client
            session_id: Session ID tu JWT

        Returns:
            GatewayResponse voi ket qua.
        """
        request_id = ""
        entity_id = raw_input.get("entity_id", "unknown")
        action = raw_input.get("action", "unknown")
        decision = "DENIED"
        deny_reason = None
        safety_level_str = ""
        ha_result_str = None
        ha_response_ms = None

        try:
            # ── Step 1: Sanitize ───────────────────────────
            try:
                clean_cmd = sanitize(raw_input, user_id)
                request_id = clean_cmd.request_id
                entity_id = clean_cmd.entity_id
                action = clean_cmd.action
            except SanitizerError as e:
                deny_reason = e.error_code
                await self._log_audit(
                    request_id=request_id or "sanitizer-fail",
                    user_id=user_id,
                    ip_address=ip_address,
                    session_id=session_id,
                    entity_id=entity_id,
                    action=action,
                    params="{}",
                    decision="DENIED",
                    deny_reason=e.error_code,
                    safety_level="",
                )
                return GatewayResponse(
                    request_id=request_id or "sanitizer-fail",
                    success=False,
                    decision="DENIED",
                    safety_level="",
                    error_code=e.error_code,
                    error_msg=e.message,
                )

            # ── Step 2: Rule Engine ────────────────────────
            try:
                safety_level = evaluate(clean_cmd.entity_id, clean_cmd.action)
                safety_level_str = safety_level.value
                decision = "APPROVED"
            except ActionDeniedError:
                decision = "DENIED"
                deny_reason = "ACTION_DENIED"
                safety_level_str = "critical"

                await self._log_audit(
                    request_id=request_id,
                    user_id=user_id,
                    ip_address=ip_address,
                    session_id=session_id,
                    entity_id=entity_id,
                    action=action,
                    params=json.dumps(clean_cmd.params),
                    decision="DENIED",
                    deny_reason="ACTION_DENIED",
                    safety_level="critical",
                )
                return GatewayResponse(
                    request_id=request_id,
                    success=False,
                    decision="DENIED",
                    safety_level="critical",
                    error_code="ACTION_DENIED",
                    error_msg=GATEWAY_ERRORS["ACTION_DENIED"],
                )

            except ActionNotPermittedError:
                decision = "DENIED"
                deny_reason = "ACTION_NOT_PERMITTED"

                await self._log_audit(
                    request_id=request_id,
                    user_id=user_id,
                    ip_address=ip_address,
                    session_id=session_id,
                    entity_id=entity_id,
                    action=action,
                    params=json.dumps(clean_cmd.params),
                    decision="DENIED",
                    deny_reason="ACTION_NOT_PERMITTED",
                    safety_level="",
                )
                return GatewayResponse(
                    request_id=request_id,
                    success=False,
                    decision="DENIED",
                    safety_level="",
                    error_code="ACTION_NOT_PERMITTED",
                    error_msg=GATEWAY_ERRORS["ACTION_NOT_PERMITTED"],
                )

            except NoRuleFoundError:
                decision = "DENIED"
                deny_reason = "NO_RULE_FOUND"

                await self._log_audit(
                    request_id=request_id,
                    user_id=user_id,
                    ip_address=ip_address,
                    session_id=session_id,
                    entity_id=entity_id,
                    action=action,
                    params=json.dumps(clean_cmd.params),
                    decision="DENIED",
                    deny_reason="NO_RULE_FOUND",
                    safety_level="",
                )
                return GatewayResponse(
                    request_id=request_id,
                    success=False,
                    decision="DENIED",
                    safety_level="",
                    error_code="NO_RULE_FOUND",
                    error_msg=GATEWAY_ERRORS["NO_RULE_FOUND"],
                )

            # ── Step 2b: Check confirmation ────────────────
            needs_confirm = requires_confirmation(
                clean_cmd.entity_id, clean_cmd.action
            )
            if needs_confirm and safety_level in (SafetyLevel.WARNING, SafetyLevel.CRITICAL):
                await self._log_audit(
                    request_id=request_id,
                    user_id=user_id,
                    ip_address=ip_address,
                    session_id=session_id,
                    entity_id=entity_id,
                    action=action,
                    params=json.dumps(clean_cmd.params),
                    decision="APPROVED",
                    deny_reason=None,
                    safety_level=safety_level_str,
                    ha_result="PENDING_CONFIRMATION",
                )
                return GatewayResponse(
                    request_id=request_id,
                    success=True,
                    decision="APPROVED",
                    safety_level=safety_level_str,
                    requires_confirmation=True,
                    error_msg=GATEWAY_ERRORS["CONFIRMATION_REQUIRED"],
                )

            # ── Step 3: Execute (call HA) ──────────────────
            ha_result_dict = None
            start_time = time.monotonic()

            if self._ha_client is not None:
                try:
                    ha_result_dict = await self._ha_client.call_service(
                        entity_id=clean_cmd.entity_id,
                        action=clean_cmd.action,
                        params=clean_cmd.params,
                    )
                    ha_result_str = "SUCCESS"
                except Exception as e:
                    ha_result_str = "FAILED"
                    logger.error("[GATEWAY] HA call failed: %s", str(e)[:200])
            else:
                # HA client chua co — mock response (dev mode)
                ha_result_dict = {
                    "entity_id": clean_cmd.entity_id,
                    "state": "executed",
                    "mock": True,
                }
                ha_result_str = "SUCCESS_MOCK"

            ha_response_ms = int((time.monotonic() - start_time) * 1000)

            # ── Step 4: Audit Log ──────────────────────────
            await self._log_audit(
                request_id=request_id,
                user_id=user_id,
                ip_address=ip_address,
                session_id=session_id,
                entity_id=entity_id,
                action=action,
                params=json.dumps(clean_cmd.params),
                decision="APPROVED",
                deny_reason=None,
                safety_level=safety_level_str,
                ha_result=ha_result_str,
                ha_response_ms=ha_response_ms,
            )

            return GatewayResponse(
                request_id=request_id,
                success=True,
                decision="APPROVED",
                safety_level=safety_level_str,
                ha_result=ha_result_dict,
                ha_response_ms=ha_response_ms,
            )

        except Exception as e:
            # Catch-all — KHONG BAO GIO de Gateway crash
            logger.exception("[GATEWAY] Unexpected error: %s", str(e)[:200])
            await self._log_audit(
                request_id=request_id or "unknown",
                user_id=user_id,
                ip_address=ip_address,
                session_id=session_id,
                entity_id=entity_id,
                action=action,
                params="{}",
                decision="DENIED",
                deny_reason="INTERNAL_ERROR",
                safety_level="",
            )
            return GatewayResponse(
                request_id=request_id or "unknown",
                success=False,
                decision="DENIED",
                safety_level="",
                error_code="INTERNAL_ERROR",
                error_msg=GATEWAY_ERRORS["INTERNAL_ERROR"],
            )

    async def _log_audit(
        self,
        request_id: str,
        user_id: str,
        ip_address: str,
        session_id: str,
        entity_id: str,
        action: str,
        params: str,
        decision: str,
        deny_reason: str | None,
        safety_level: str,
        ha_result: str | None = None,
        ha_response_ms: int | None = None,
    ) -> None:
        """Helper de ghi audit log."""
        record = AuditRecord(
            request_id=request_id,
            user_id=user_id,
            ip_address=ip_address,
            session_id=session_id,
            entity_id=entity_id,
            action=action,
            params=params,
            decision=decision,
            deny_reason=deny_reason,
            safety_level=safety_level,
            ha_result=ha_result,
            ha_response_ms=ha_response_ms,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await self._audit.log(record)


# ── Singleton accessor ────────────────────────────────────

def get_gateway() -> SecurityGateway:
    """Tra ve singleton SecurityGateway instance."""
    return SecurityGateway()

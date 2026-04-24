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
from src.core.security.rate_limiter import (
    get_rate_limiter,
    RateLimitResult,
)
from src.core.security.rbac import check_permission, RBACError

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
    pipeline_steps: list[dict] | None = None  # Chi tiet tung buoc pipeline


# ── Error Codes ────────────────────────────────────────────

GATEWAY_ERRORS = {
    "SANITIZER_ERROR": "Dữ liệu đầu vào không hợp lệ",
    "ACTION_DENIED": "Hành động bị chặn vĩnh viễn",
    "ACTION_NOT_PERMITTED": "Hành động không được phép",
    "NO_RULE_FOUND": "Thiết bị không có quy tắc — bị chặn mặc định",
    "CONFIRMATION_REQUIRED": "Cần xác nhận trước khi thực hiện",
    "EXECUTION_ERROR": "Lỗi khi thực thi lệnh",
    "INTERNAL_ERROR": "Lỗi hệ thống nội bộ",
    "RATE_LIMITED": "Bạn gửi quá nhiều lệnh — vui lòng chờ chút",
    "CIRCUIT_OPEN": "Hệ thống tạm ngưng — vui lòng thử lại sau",
    "RBAC_DENIED": "Bạn không có quyền thực hiện lệnh này",
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
        self._rate_limiter = get_rate_limiter()
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
        user_roles: list[str] | None = None,
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

        # Pipeline step tracker
        steps: list[dict] = []
        pipeline_start = time.monotonic()

        def _step(name: str, status: str, detail: str = ""):
            """Ghi 1 step vào pipeline log."""
            elapsed = int((time.monotonic() - pipeline_start) * 1000)
            steps.append({
                "name": name,
                "status": status,  # pass | fail | skip | pending
                "detail": detail,
                "elapsed_ms": elapsed,
            })

        def _make_response(**kwargs) -> GatewayResponse:
            """Tạo GatewayResponse kèm pipeline_steps."""
            kwargs["pipeline_steps"] = steps
            return GatewayResponse(**kwargs)

        try:
            # ── Step 0: Rate Limit ─────────────────────────
            rl_result = self._rate_limiter.check_rate_limit(
                user_id=user_id,
                entity_id=entity_id if entity_id != "unknown" else None,
            )
            if rl_result.result == RateLimitResult.RATE_LIMITED:
                _step("Rate Limiter", "fail", rl_result.reason or "Quá nhiều request")
                await self._log_audit(
                    request_id="rate-limited",
                    user_id=user_id,
                    ip_address=ip_address,
                    session_id=session_id,
                    entity_id=entity_id,
                    action=action,
                    params="{}",
                    decision="RATE_LIMITED",
                    deny_reason="RATE_LIMITED",
                    safety_level="",
                )
                return _make_response(
                    request_id="rate-limited",
                    success=False,
                    decision="RATE_LIMITED",
                    safety_level="",
                    error_code="RATE_LIMITED",
                    error_msg=GATEWAY_ERRORS["RATE_LIMITED"],
                )
            _step("Rate Limiter", "pass", f"Remaining: {rl_result.remaining}")

            # ── Step 1: Sanitize ───────────────────────────
            try:
                clean_cmd = sanitize(raw_input, user_id)
                request_id = clean_cmd.request_id
                entity_id = clean_cmd.entity_id
                action = clean_cmd.action
                _step("Sanitizer", "pass", f"entity={entity_id} action={action}")
            except SanitizerError as e:
                _step("Sanitizer", "fail", e.message)
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
                return _make_response(
                    request_id=request_id or "sanitizer-fail",
                    success=False,
                    decision="DENIED",
                    safety_level="",
                    error_code=e.error_code,
                    error_msg=e.message,
                )

            # ── Step 1b: RBAC Check ────────────────────────
            if user_roles:
                try:
                    check_permission(user_roles, clean_cmd.entity_id, clean_cmd.action)
                    _step("RBAC", "pass", f"roles={user_roles}")
                except RBACError as e:
                    _step("RBAC", "fail", str(e))
                    await self._log_audit(
                        request_id=request_id,
                        user_id=user_id,
                        ip_address=ip_address,
                        session_id=session_id,
                        entity_id=entity_id,
                        action=action,
                        params=json.dumps(clean_cmd.params),
                        decision="DENIED",
                        deny_reason="RBAC_DENIED",
                        safety_level="",
                    )
                    return _make_response(
                        request_id=request_id,
                        success=False,
                        decision="DENIED",
                        safety_level="",
                        error_code="RBAC_DENIED",
                        error_msg=GATEWAY_ERRORS["RBAC_DENIED"],
                    )
            else:
                _step("RBAC", "skip", "No roles provided")

            # ── Step 2: Rule Engine ────────────────────────
            try:
                safety_level = evaluate(clean_cmd.entity_id, clean_cmd.action)
                safety_level_str = safety_level.value
                decision = "APPROVED"
                _step("Rule Engine", "pass", f"level={safety_level_str}")
            except ActionDeniedError:
                _step("Rule Engine", "fail", "ACTION_DENIED (chặn vĩnh viễn)")
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
                return _make_response(
                    request_id=request_id,
                    success=False,
                    decision="DENIED",
                    safety_level="critical",
                    error_code="ACTION_DENIED",
                    error_msg=GATEWAY_ERRORS["ACTION_DENIED"],
                )

            except ActionNotPermittedError:
                _step("Rule Engine", "fail", "ACTION_NOT_PERMITTED")
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
                return _make_response(
                    request_id=request_id,
                    success=False,
                    decision="DENIED",
                    safety_level="",
                    error_code="ACTION_NOT_PERMITTED",
                    error_msg=GATEWAY_ERRORS["ACTION_NOT_PERMITTED"],
                )

            except NoRuleFoundError:
                _step("Rule Engine", "fail", "NO_RULE_FOUND")
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
                return _make_response(
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
                _step("Confirmation", "pending", f"level={safety_level_str}")
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
                return _make_response(
                    request_id=request_id,
                    success=True,
                    decision="APPROVED",
                    safety_level=safety_level_str,
                    requires_confirmation=True,
                    error_msg=GATEWAY_ERRORS["CONFIRMATION_REQUIRED"],
                )
            else:
                _step("Confirmation", "skip", "Không cần xác nhận")

            # ── Step 2c: Circuit Breaker ───────────────────
            cb_result = self._rate_limiter.check_circuit()
            if cb_result.result == RateLimitResult.CIRCUIT_OPEN:
                _step("Circuit Breaker", "fail", "OPEN — HA không khả dụng")
                await self._log_audit(
                    request_id=request_id,
                    user_id=user_id,
                    ip_address=ip_address,
                    session_id=session_id,
                    entity_id=entity_id,
                    action=action,
                    params=json.dumps(clean_cmd.params),
                    decision="DENIED",
                    deny_reason="CIRCUIT_OPEN",
                    safety_level=safety_level_str,
                )
                return _make_response(
                    request_id=request_id,
                    success=False,
                    decision="DENIED",
                    safety_level=safety_level_str,
                    error_code="CIRCUIT_OPEN",
                    error_msg=GATEWAY_ERRORS["CIRCUIT_OPEN"],
                )
            _step("Circuit Breaker", "pass", "CLOSED")

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
                    self._rate_limiter.circuit.record_success()
                except Exception as e:
                    ha_result_str = "FAILED"
                    self._rate_limiter.circuit.record_failure()
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
            _step("Execute HA", "pass" if "SUCCESS" in (ha_result_str or "") else "fail",
                  f"{ha_result_str} ({ha_response_ms}ms)")

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
            _step("Audit Log", "pass", f"req={request_id[:8]}")

            return _make_response(
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

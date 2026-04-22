"""
Sanitizer — Input Validation & Cleaning
=========================================
Validate va clean moi input tu LLM truoc khi chuyen sang Rule Engine.

Luong xu ly:
  raw dict (tu LLM)
    → strip + lowercase
    → regex validate entity_id
    → regex validate action
    → validate params theo entity_type (Pydantic schema)
    → inject server-side metadata (user_id, request_id, timestamp)
    → return CleanCommand

Nguyen tac:
- KHONG tin bat ky data nao tu LLM
- Moi field deu duoc validate rieng
- Error messages KHONG lo stack trace
- Injection patterns bi strip truoc khi validate
"""

from __future__ import annotations

import re
import uuid
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field

from pydantic import ValidationError

from src.tools.schemas import get_schema_for_entity

logger = logging.getLogger(__name__)

# ── Regex Patterns ─────────────────────────────────────────
ENTITY_ID_PATTERN = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")
ACTION_PATTERN = re.compile(r"^[a-z_]+$")

# ── Injection detection patterns ───────────────────────────
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous\s+)?(rules|instructions|commands)", re.I),
    re.compile(r"system\s*prompt", re.I),
    re.compile(r"you\s+are\s+now", re.I),
    re.compile(r"override\s+(security|rules|access)", re.I),
    re.compile(r"admin\s+mode", re.I),
    re.compile(r"debug\s+mode", re.I),
    re.compile(r"forget\s+(everything|all|previous)", re.I),
    re.compile(r"pretend\s+(you|to\s+be)", re.I),
    re.compile(r"act\s+as\s+(if|a|an)", re.I),
    re.compile(r"bypass\s+(security|auth|rule)", re.I),
]


# ── Data Models ────────────────────────────────────────────

@dataclass(frozen=True)
class CleanCommand:
    """Command da duoc validate va clean — an toan de chuyen sang Rule Engine."""
    entity_id: str
    action: str
    params: dict
    user_id: str
    request_id: str
    timestamp: datetime


class SanitizerError(Exception):
    """Base error cho Sanitizer."""
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)


# ── Error Codes (khong lo stack trace) ─────────────────────

SANITIZER_ERRORS = {
    "INVALID_ENTITY_FORMAT": "Định dạng Entity ID không hợp lệ",
    "INVALID_ACTION_FORMAT": "Định dạng Action không hợp lệ",
    "MISSING_ENTITY_ID": "Thiếu entity_id",
    "MISSING_ACTION": "Thiếu action",
    "PARAM_VALIDATION_ERROR": "Tham số không hợp lệ",
    "UNKNOWN_ENTITY_TYPE": "Loại entity không được hỗ trợ",
    "INJECTION_DETECTED": "Phát hiện nội dung không hợp lệ",
    "INVALID_INPUT_TYPE": "Input phải là dictionary",
}


# ── Core Functions ─────────────────────────────────────────

def _check_injection(text: str) -> bool:
    """Kiem tra text co chua injection pattern khong."""
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _clean_string(value: str) -> str:
    """Strip va lowercase mot string."""
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def sanitize(
    raw_input: dict,
    user_id: str,
) -> CleanCommand:
    """
    Validate va clean raw input tu LLM.

    Args:
        raw_input: Dict tu LLM, vd: {"entity_id": "light.phong_ngu", "action": "turn_on"}
        user_id: User ID tu JWT (server-side, khong tin client)

    Returns:
        CleanCommand da validate.

    Raises:
        SanitizerError: Neu input khong hop le.
    """
    # ── Validate input type ────────────────────────────────
    if not isinstance(raw_input, dict):
        logger.warning("[SANITIZER] Invalid input type: %s", type(raw_input))
        raise SanitizerError("INVALID_INPUT_TYPE", SANITIZER_ERRORS["INVALID_INPUT_TYPE"])

    # ── Extract va clean fields ────────────────────────────
    raw_entity = raw_input.get("entity_id", "")
    raw_action = raw_input.get("action", "")
    raw_params = raw_input.get("params", {})

    # Ensure params is dict
    if not isinstance(raw_params, dict):
        raw_params = {}

    entity_id = _clean_string(raw_entity)
    action = _clean_string(raw_action)

    # ── Check injection in all string fields ───────────────
    all_text = f"{raw_entity} {raw_action} {str(raw_params)}"
    if _check_injection(all_text):
        logger.warning(
            "[SANITIZER] INJECTION DETECTED in input: %s",
            all_text[:200],
        )
        raise SanitizerError("INJECTION_DETECTED", SANITIZER_ERRORS["INJECTION_DETECTED"])

    # ── Validate entity_id ─────────────────────────────────
    if not entity_id:
        raise SanitizerError("MISSING_ENTITY_ID", SANITIZER_ERRORS["MISSING_ENTITY_ID"])

    if not ENTITY_ID_PATTERN.match(entity_id):
        logger.warning("[SANITIZER] Invalid entity format: %s", entity_id[:50])
        raise SanitizerError("INVALID_ENTITY_FORMAT", SANITIZER_ERRORS["INVALID_ENTITY_FORMAT"])

    # ── Validate action ────────────────────────────────────
    if not action:
        raise SanitizerError("MISSING_ACTION", SANITIZER_ERRORS["MISSING_ACTION"])

    if not ACTION_PATTERN.match(action):
        logger.warning("[SANITIZER] Invalid action format: %s", action[:50])
        raise SanitizerError("INVALID_ACTION_FORMAT", SANITIZER_ERRORS["INVALID_ACTION_FORMAT"])

    # ── Validate params via Pydantic schema ────────────────
    schema_class = get_schema_for_entity(entity_id)
    if schema_class is None:
        logger.warning("[SANITIZER] Unknown entity type: %s", entity_id)
        raise SanitizerError("UNKNOWN_ENTITY_TYPE", SANITIZER_ERRORS["UNKNOWN_ENTITY_TYPE"])

    try:
        validated = schema_class(
            entity_id=entity_id,
            action=action,
            **raw_params,
        )
        # Extract validated params (exclude entity_id and action)
        clean_params = {
            k: v
            for k, v in validated.model_dump().items()
            if k not in ("entity_id", "action") and v is not None
        }
    except ValidationError as e:
        logger.warning("[SANITIZER] Param validation failed: %s", str(e)[:200])
        raise SanitizerError("PARAM_VALIDATION_ERROR", SANITIZER_ERRORS["PARAM_VALIDATION_ERROR"])

    # ── Build CleanCommand ─────────────────────────────────
    request_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc)

    logger.info(
        "[SANITIZER] CLEAN: entity=%s action=%s user=%s req=%s",
        entity_id, action, user_id, request_id[:8],
    )

    return CleanCommand(
        entity_id=entity_id,
        action=action,
        params=clean_params,
        user_id=user_id,
        request_id=request_id,
        timestamp=timestamp,
    )

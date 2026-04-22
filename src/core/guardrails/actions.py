"""
Guardrails Actions — Custom check functions
=============================================
Cac ham nay duoc goi boi NeMo Guardrails flows.
Hien tai: dung Sanitizer da co (khong can NeMo runtime).
Khi can: cai `nemoguardrails` va dang ky cac action nay.
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)


# ── Injection Patterns (shared with sanitizer.py) ───

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous",
    r"ignore\s+(all\s+)?rules",
    r"ignore\s+(all\s+)?instructions",
    r"system\s*prompt",
    r"you\s+are\s+now",
    r"pretend\s+(you\s+are|to\s+be)",
    r"act\s+as",
    r"bypass\s+security",
    r"override\s+(all|security|rules)",
    r"(DAN|developer)\s+mode",
    r"jailbreak",
    r"reveal\s+(your|system|the)\s+(prompt|instructions|rules)",
    r"what\s+are\s+your\s+(rules|instructions|guidelines)",
    r"forget\s+(all|everything|your)",
    r"disregard\s+(all|previous|your)",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


# ── Off-topic detection ─────────────────────────

SMART_HOME_KEYWORDS = [
    "den", "light", "bat", "tat", "mo", "dong", "khoa",
    "quat", "fan", "dieu hoa", "nhiet do", "do am",
    "cam bien", "sensor", "bep", "cua", "phong",
    "climate", "lock", "switch", "turn", "set",
]


def check_jailbreak_attempt(text: str) -> bool:
    """Kiem tra xem co phai jailbreak attempt khong."""
    for pattern in COMPILED_PATTERNS:
        if pattern.search(text):
            logger.warning("[GUARDRAIL] Jailbreak detected: %s", text[:80])
            return True
    return False


def check_injection_patterns(text: str) -> bool:
    """Kiem tra prompt injection patterns."""
    return check_jailbreak_attempt(text)


def check_allowed_topic(text: str) -> bool:
    """Kiem tra xem cau hoi co lien quan smart home khong."""
    text_lower = text.lower()
    # Cau ngan (<= 5 tu) thuong la lenh → cho phep
    if len(text.split()) <= 5:
        return True
    # Kiem tra co keyword smart home khong
    for kw in SMART_HOME_KEYWORDS:
        if kw in text_lower:
            return True
    logger.info("[GUARDRAIL] Off-topic detected: %s", text[:80])
    return False


def check_output_safety(response: str) -> bool:
    """Kiem tra output co an toan khong."""
    danger_patterns = [
        r"(password|secret|api.?key|token)",
        r"(sudo|rm\s+-rf|exec|eval)",
        r"(hack|exploit|vulnerability)",
    ]
    for p in danger_patterns:
        if re.search(p, response, re.IGNORECASE):
            logger.warning("[GUARDRAIL] Unsafe output detected")
            return False
    return True


def check_hallucination_risk(response: str) -> bool:
    """Kiem tra risk bua dat (heuristic co ban)."""
    hallucination_phrases = [
        "toi khong biet nhung",
        "co the la",
        "toi doan rang",
    ]
    resp_lower = response.lower()
    for phrase in hallucination_phrases:
        if phrase in resp_lower:
            return True
    return False

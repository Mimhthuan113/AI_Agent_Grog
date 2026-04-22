"""
Entity Registry — Map alias tieng Viet → entity_id Home Assistant
==================================================================
Nguoi dung noi "tat den phong ngu" → he thong can biet do la "light.phong_ngu"

Registry nay lam viec do:
- Alias khong phan biet hoa thuong
- Ho tro nhieu alias cho cung 1 entity
- MVP: hardcode 20+ alias, Phase 2: load tu config/DB
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EntityInfo:
    """Thong tin 1 entity trong Home Assistant."""
    entity_id: str
    friendly_name: str
    device_type: str  # light, switch, lock, climate, sensor


# ── REGISTRY — 20+ alias tieng Viet ───────────────────────
# Key: alias (lowercase, stripped)
# Value: EntityInfo

ENTITY_REGISTRY: dict[str, EntityInfo] = {
    # ── Đèn ────────────────────────────────────────────────
    "den phong ngu": EntityInfo("light.phong_ngu", "Đèn phòng ngủ", "light"),
    "den ngu": EntityInfo("light.phong_ngu", "Đèn phòng ngủ", "light"),
    "den phong khach": EntityInfo("light.phong_khach", "Đèn phòng khách", "light"),
    "den khach": EntityInfo("light.phong_khach", "Đèn phòng khách", "light"),
    "den ban hoc": EntityInfo("light.ban_hoc", "Đèn bàn học", "light"),
    "den hoc": EntityInfo("light.ban_hoc", "Đèn bàn học", "light"),
    "den bep": EntityInfo("light.bep", "Đèn bếp", "light"),
    "den nha tam": EntityInfo("light.nha_tam", "Đèn nhà tắm", "light"),
    "den hanh lang": EntityInfo("light.hanh_lang", "Đèn hành lang", "light"),

    # ── Quạt ───────────────────────────────────────────────
    "quat phong ngu": EntityInfo("switch.fan_phong_ngu", "Quạt phòng ngủ", "switch"),
    "quat ngu": EntityInfo("switch.fan_phong_ngu", "Quạt phòng ngủ", "switch"),
    "quat phong khach": EntityInfo("switch.fan_phong_khach", "Quạt phòng khách", "switch"),
    "quat khach": EntityInfo("switch.fan_phong_khach", "Quạt phòng khách", "switch"),

    # ── Bếp ────────────────────────────────────────────────
    "bep": EntityInfo("switch.kitchen_stove", "Bếp điện", "switch"),
    "bep dien": EntityInfo("switch.kitchen_stove", "Bếp điện", "switch"),
    "lo vi song": EntityInfo("switch.kitchen_microwave", "Lò vi sóng", "switch"),

    # ── Điều hòa ───────────────────────────────────────────
    "dieu hoa": EntityInfo("climate.phong_ngu", "Điều hòa phòng ngủ", "climate"),
    "dieu hoa phong ngu": EntityInfo("climate.phong_ngu", "Điều hòa phòng ngủ", "climate"),
    "dieu hoa phong khach": EntityInfo("climate.phong_khach", "Điều hòa phòng khách", "climate"),
    "may lanh": EntityInfo("climate.phong_ngu", "Điều hòa phòng ngủ", "climate"),

    # ── Khóa ───────────────────────────────────────────────
    "khoa cua": EntityInfo("lock.cua_chinh", "Khóa cửa chính", "lock"),
    "khoa cua chinh": EntityInfo("lock.cua_chinh", "Khóa cửa chính", "lock"),
    "cua chinh": EntityInfo("lock.cua_chinh", "Khóa cửa chính", "lock"),

    # ── Cảm biến ───────────────────────────────────────────
    "nhiet do": EntityInfo("sensor.nhiet_do_phong", "Cảm biến nhiệt độ", "sensor"),
    "nhiet do phong": EntityInfo("sensor.nhiet_do_phong", "Cảm biến nhiệt độ", "sensor"),
    "do am": EntityInfo("sensor.do_am_phong", "Cảm biến độ ẩm", "sensor"),
    "cua ra vao": EntityInfo("binary_sensor.cua_ra_vao", "Cảm biến cửa", "sensor"),
}

# ── Mapping action tieng Viet → action code ────────────────

ACTION_MAP: dict[str, str] = {
    # Bat/Tat
    "bat": "turn_on",
    "mo": "turn_on",
    "tat": "turn_off",
    "dong": "turn_off",
    "ngat": "turn_off",
    "dung": "turn_off",
    "tat di": "turn_off",
    "bat len": "turn_on",
    "bat di": "turn_on",

    # Khoa
    "khoa": "lock",
    "khoa lai": "lock",
    "mo khoa": "unlock",  # Se bi Rule Engine chan

    # Dieu hoa
    "dat nhiet do": "set_temperature",
    "chinh nhiet do": "set_temperature",
    "tang nhiet do": "set_temperature",
    "giam nhiet do": "set_temperature",
    "che do": "set_hvac_mode",

    # Den
    "chinh do sang": "set_brightness",
    "tang do sang": "set_brightness",
    "giam do sang": "set_brightness",
    "doi mau": "set_color",

    # Cam bien
    "xem": "get_state",
    "doc": "get_state",
    "kiem tra": "get_state",
    "trang thai": "get_state",
    "bao nhieu": "get_state",
}


def _normalize(text: str) -> str:
    """Chuẩn hóa text: lowercase, bỏ dấu, strip."""
    import unicodedata
    text = text.strip().lower()
    # Xử lý đ/Đ trước (NFD không strip được)
    text = text.replace("đ", "d").replace("Đ", "D")
    # Bỏ dấu tiếng Việt
    nfkd = unicodedata.normalize("NFD", text)
    no_accent = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    # Bỏ ký tự đặc biệt
    no_accent = "".join(c for c in no_accent if c.isalnum() or c == " ")
    # Bỏ khoảng trắng thừa
    return " ".join(no_accent.split())


def resolve_entity(text: str) -> EntityInfo | None:
    """
    Tim entity tu text tieng Viet.

    Args:
        text: "den phong ngu", "bep", "dieu hoa"...

    Returns:
        EntityInfo hoac None.
    """
    normalized = _normalize(text)

    # Tim chinh xac
    if normalized in ENTITY_REGISTRY:
        info = ENTITY_REGISTRY[normalized]
        logger.info("[REGISTRY] Resolved: '%s' -> %s", text, info.entity_id)
        return info

    # Tim gan dung (substring match)
    for alias, info in ENTITY_REGISTRY.items():
        if alias in normalized or normalized in alias:
            logger.info("[REGISTRY] Fuzzy resolved: '%s' -> %s", text, info.entity_id)
            return info

    logger.warning("[REGISTRY] Cannot resolve: '%s'", text)
    return None


def resolve_action(text: str) -> str | None:
    """
    Tim action tu text tieng Viet.

    Args:
        text: "bat", "tat", "khoa"...

    Returns:
        Action code hoac None.
    """
    normalized = _normalize(text)

    if normalized in ACTION_MAP:
        return ACTION_MAP[normalized]

    # Tim substring
    for alias, action in ACTION_MAP.items():
        if alias in normalized:
            return action

    return None


def get_all_entities() -> list[dict]:
    """Tra ve danh sach tat ca entities (cho API)."""
    seen = set()
    result = []
    for alias, info in ENTITY_REGISTRY.items():
        if info.entity_id not in seen:
            seen.add(info.entity_id)
            result.append({
                "entity_id": info.entity_id,
                "friendly_name": info.friendly_name,
                "device_type": info.device_type,
            })
    return result

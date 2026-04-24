"""
App Action Router — Phân phối intent tới provider phù hợp
============================================================
2 tầng parse:
  1. Smart Regex — xử lý câu tự nhiên "mở ytb kiếm bài sóng gió"
  2. LLM Fallback — nếu regex không parse được hết params

Không gán cứng số điện thoại / query — extract từ câu nói.
"""
from __future__ import annotations

import re
import json
import logging
from src.core.app_actions.base import AppActionResult
from src.core.app_actions.providers import PROVIDER_MAP, ALL_PROVIDERS
from src.core.app_actions.system_executor import (
    resolve_app_name, open_app, open_url_default_browser, open_explorer,
)
from src.core.app_actions.file_ops import create_folder, create_file, write_to_existing_file

logger = logging.getLogger(__name__)


# ── Smart Patterns (ưu tiên trên → dưới) ──────────────────
# Mỗi pattern: (regex, provider, action, named groups → params)
# Dùng named groups để extract params linh hoạt

SMART_PATTERNS: list[tuple[str, str, str]] = [
    # ── YouTube: "mở ytb kiếm/tìm bài X" (có dấu + không dấu) ──
    (r"(?:mở|mo)\s*(?:youtube|ytb|yt)\s+(?:kiếm|kiem|tìm|tim|search|nghe|xem|phát|phat|bật|bat)\s+(?:bài\s*|bai\s*)?(?:hát\s*|hat\s*)?(?:video\s*)?(?P<query>.+)",
     "youtube", "youtube_search"),
    (r"(?:tìm|tim|kiếm|kiem|search|xem)\s+(?:video|bài|bai|clip)\s+(?:trên\s+|tren\s+)?(?:youtube|ytb|yt)\s*(?P<query>.*)?",
     "youtube", "youtube_search"),
    (r"(?:tìm|tim|kiếm|kiem|xem)\s+(?:trên\s+|tren\s+)?(?:youtube|ytb)\s+(?P<query>.+)",
     "youtube", "youtube_search"),
    (r"(?:mở|mo)\s+(?:youtube|ytb|yt)\s+(?P<query>.+)",
     "youtube", "youtube_search"),
    (r"(?:mở|mo|vào|vao)\s+(?:youtube|ytb|yt)\s*$",
     "youtube", "open_youtube"),

    # ── Spotify ──
    (r"(?:mở|mo)\s*spotify\s+(?:nghe|phat|phát|tìm|tim|kiếm|kiem|bật|bat|play)\s+(?:bài\s*|bai\s*)?(?:hát\s*|hat\s*)?(?P<query>.+)",
     "spotify", "spotify_search"),
    (r"(?:nghe|phát|phat|bật|bat|play)\s+(?:nhạc|nhac|bài|bai)\s+(?:trên\s+|tren\s+)?(?:spotify\s+)?(?P<query>.+)",
     "spotify", "spotify_search"),
    (r"(?:mở|mo|vào|vao)\s+spotify\s*$",
     "spotify", "open_spotify"),

    # ── Phone ──
    (r"(?:gọi|goi|call)\s+(?:cho\s+|điện\s+cho\s+|dien\s+cho\s+|điện\s+|dien\s+|số\s+|so\s+)?(?P<phone>\+?\d[\d\s\-\.]{7,})",
     "phone", "call"),

    # ── SMS ──
    (r"(?:nhắn\s*tin|nhan\s*tin|gửi\s*sms|gui\s*sms|tin\s*nhắn|tin\s*nhan)\s+(?:cho\s+)?(?P<phone>\+?\d[\d\s\-\.]{7,})(?:\s+(?:nội\s*dung|noi\s*dung|nd|rằng|rang|là|la|:)\s*(?P<body>.+))?",
     "sms", "send_sms"),

    # ── Zalo ──
    (r"(?:nhắn|nhan)\s*zalo\s+(?:cho\s+)?(?P<phone>\+?\d[\d\s\-\.]{7,})(?:\s+(?:nội\s*dung|noi\s*dung|nd|:)\s*(?P<body>.+))?",
     "zalo", "zalo_chat"),
    (r"(?:gọi|goi)\s*zalo\s+(?:cho\s+)?(?P<phone>\+?\d[\d\s\-\.]{7,})",
     "zalo", "zalo_call"),
    (r"zalo\s+(?:cho\s+)?(?P<phone>\+?\d[\d\s\-\.]{7,})",
     "zalo", "zalo_chat"),
    (r"(?:mở|mo|vào|vao)\s+zalo\s*$",
     "zalo", "open_zalo"),

    # ── Facebook ──
    (r"(?:mở|mo|vào|vao)\s+(?:facebook|fb)\s*$", "facebook", "open_fb"),
    (r"(?:mở|mo|vào|vao)\s+messenger\s*$", "facebook", "open_messenger"),

    # ── Google Maps ──
    (r"(?:chỉ\s*đường|chi\s*duong|dẫn\s*đường|dan\s*duong|đi\s*đến|di\s*den|tìm\s*đường|tim\s*duong|navigate)\s+(?:đến\s+|den\s+|tới\s+|toi\s+)?(?P<destination>.+)",
     "maps", "navigate"),
    (r"(?:tìm|tim|kiếm|kiem)\s+(?:quán|quan|nhà\s*hàng|nha\s*hang|tiệm|tiem|chỗ|cho|nơi|noi|địa\s*điểm|dia\s*diem)\s+(?P<query>.+)",
     "maps", "search_place"),
    (r"(?P<query>.+?)\s+(?:gần\s*đây|gan\s*day|ở\s*đâu|o\s*dau|chỗ\s*nào|cho\s*nao)",
     "maps", "search_place"),
    (r"(?:mở|mo|vào|vao)\s+(?:bản\s*đồ|ban\s*do|maps|google\s*maps)\s*$",
     "maps", "open_maps"),

    # ── Gmail ──
    (r"(?:gửi|gui|soạn|soan|viết|viet)\s+email\s+(?:cho\s+)?(?P<to>[\w\.\-]+@[\w\.\-]+\.\w+)?(?:\s+tiêu\s*đề\s*:?\s*(?P<subject>.+?))?(?:\s+nội\s*dung\s*:?\s*(?P<body>.+))?$",
     "gmail", "send_email"),
    (r"(?:mở|mo|vào|vao)\s+(?:email|gmail)\s*$", "gmail", "open_gmail"),

    # ── Camera ──
    (r"(?:mở|mo)\s*camera", "camera", "open_camera"),
    (r"(?:chụp|chup)\s*(?:ảnh|anh|hình|hinh)", "camera", "open_camera"),

    # ── TikTok ──
    (r"(?:mở|mo|vào|vao|xem)\s+tiktok\s*$", "tiktok", "open_tiktok"),

    # ── Cốc Cốc ──
    (r"(?:mở|mo)\s*(?:cốc\s*cốc|coc\s*coc)\s+(?:tìm|tim|kiếm|kiem|search)\s+(?P<query>.+)",
     "coccoc", "coccoc_search"),
    (r"(?:mở|mo|vào|vao)\s+(?:cốc\s*cốc|coc\s*coc)",
     "coccoc", "open_coccoc"),

    # ── Web Search ──
    (r"(?:tìm\s*kiếm|tim\s*kiem|search|google)\s+(?P<query>.+)", "web", "web_search"),
    (r"(?:mở\s*trang|mo\s*trang|mở\s*web|mo\s*web|truy\s*cập|truy\s*cap)\s+(?P<url>[\w\.\-]+\.\w{2,}.*)", "web", "open_url"),

    # ── File Operations ──
    (r"(?:tạo|tao)\s+(?:folder|thư\s*mục|thu\s*muc|foder)\s+(?:tên\s+|ten\s+)?(?P<folder_name>[\w\s\.\-]+?)(?:\s+(?:trên|tren|[ởơ]|o|tại|tai)\s+(?P<location>[\w\s]+))?$",
     "file_ops", "create_folder"),
    (r"(?:tạo|tao)\s+(?:file|tập\s*tin|tap\s*tin)\s+(?:tên\s+|ten\s+)?(?P<file_name>[\w\s\.\-]+?)(?:\s+(?:nội\s*dung|noi\s*dung|viết|viet|ghi)\s+(?P<content>.+?))?(?:\s+(?:trên|tren|[ởơ]|o|tại|tai)\s+(?P<file_location>[\w\s]+))?$",
     "file_ops", "create_file"),
]


def parse_app_intent(text: str) -> dict | None:
    """
    Parse user text thành app action intent.

    Dùng smart regex với named groups để extract params tự nhiên:
    - "mở youtube kiếm bài sóng gió" → youtube_search(query="sóng gió")
    - "gọi cho 0987654321" → call(phone="0987654321")
    - "nhắn zalo cho 0123456789 nội dung em đã về" → zalo_chat(phone=..., body=...)

    Returns:
        {"provider": "youtube", "action": "youtube_search", "params": {"query": "sóng gió"}}
        hoặc None nếu không match.
    """
    text_lower = text.lower().strip()

    for pattern, provider, action in SMART_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            # Extract named groups thành params
            params = {k: v.strip() for k, v in match.groupdict().items() if v and v.strip()}

            # Clean phone numbers
            if "phone" in params:
                params["phone"] = params["phone"].replace(" ", "").replace("-", "").replace(".", "")

            # Clean URL
            if "url" in params and not params["url"].startswith(("http://", "https://")):
                params["url"] = f"https://{params['url']}"

            logger.info(
                "[APP_ROUTER] Smart matched: provider=%s action=%s params=%s",
                provider, action, params,
            )
            return {
                "provider": provider,
                "action": action,
                "params": params,
            }

    # ── Fallback: simple keyword matching ──
    result = _fallback_parse(text_lower)
    if result:
        return result

    # ── Generic: "mở [tên app bất kỳ]" → thử tìm trong system_executor ──
    return _generic_app_parse(text_lower)


def _fallback_parse(text_lower: str) -> dict | None:
    """Fallback đơn giản cho các câu ngắn."""
    SIMPLE_MAP = [
        (["mở youtube", "mo youtube", "mở ytb", "mo ytb", "vào youtube"], "youtube", "open_youtube"),
        (["mở zalo", "mo zalo", "vào zalo", "vao zalo"], "zalo", "open_zalo"),
        (["mở facebook", "mo facebook", "mở fb", "mo fb", "vào fb"], "facebook", "open_fb"),
        (["mở messenger", "mo messenger"], "facebook", "open_messenger"),
        (["mở spotify", "mo spotify"], "spotify", "open_spotify"),
        (["mở tiktok", "mo tiktok", "vào tiktok"], "tiktok", "open_tiktok"),
        (["mở camera", "mo camera", "chụp ảnh", "chup anh"], "camera", "open_camera"),
        (["mở email", "mo email", "mở gmail", "mo gmail"], "gmail", "open_gmail"),
        (["mở bản đồ", "mo ban do", "mở maps", "mo maps"], "maps", "open_maps"),
        (["mở cốc cốc", "mo coc coc", "vào cốc cốc", "vao coc coc"], "coccoc", "open_coccoc"),
    ]

    for keywords, provider, action in SIMPLE_MAP:
        for kw in keywords:
            if kw in text_lower:
                logger.info("[APP_ROUTER] Fallback matched: %s → %s", kw, action)
                return {"provider": provider, "action": action, "params": {}}

    return None


def _generic_app_parse(text_lower: str) -> dict | None:
    """
    Generic: 'mở [tên app bất kỳ]' → thử tìm app trong system.
    Xử lý: 'mở notepad', 'mở this pc', 'mở máy tính', 'mở paint'...
    """
    import re
    # Match: mở/mo [app_name]
    m = re.match(r"(?:mở|mo)\s+(?:app\s+|ứng dụng\s+|ung dung\s+)?(.+?)(?:\s+lên|\s+đi|\s+cho tui|\s+tui)?$", text_lower)
    if not m:
        return None

    app_text = m.group(1).strip()
    app_key, display = resolve_app_name(app_text)

    if app_key:
        logger.info("[APP_ROUTER] Generic app matched: '%s' → %s (%s)", app_text, app_key, display)
        return {
            "provider": "system_app",
            "action": "open_app",
            "params": {"app_key": app_key, "display_name": display},
        }

    return None


async def execute_app_action(provider_name: str, action: str, params: dict) -> AppActionResult:
    """Thực thi app action qua provider, system executor, hoặc file ops."""

    # ── File Operations: tạo file/folder TRỰC TIẾP ──
    if provider_name == "file_ops":
        if action == "create_folder":
            name = params.get("folder_name", "").strip()
            loc = params.get("location", "desktop").strip()
            if not name:
                return AppActionResult(False, "Bạn muốn đặt tên folder là gì?", provider="file_ops")
            ok, msg = create_folder(name, loc)
            return AppActionResult(ok, msg, data={"executed_on_server": True}, provider="file_ops", action=action)

        elif action == "create_file":
            name = params.get("file_name", "").strip()
            content = params.get("content", "").strip()
            loc = params.get("file_location", "desktop").strip()
            if not name:
                return AppActionResult(False, "Bạn muốn đặt tên file là gì?", provider="file_ops")
            ok, msg = create_file(name, content, loc, open_after=True)
            return AppActionResult(ok, msg, data={"executed_on_server": True}, provider="file_ops", action=action)

        return AppActionResult(False, "Không hỗ trợ thao tác file này.", provider="file_ops")

    # ── System App: mở app trực tiếp trên OS ──
    if provider_name == "system_app" and action == "open_app":
        app_key = params.get("app_key", "")
        display = params.get("display_name", app_key)
        ok, msg = open_app(app_key)
        logger.info("[APP_ROUTER] System app: %s → %s", display, "OK" if ok else msg)
        return AppActionResult(
            ok, msg,
            data={"executed_on_server": True, "app": app_key},
            provider="system_app", action="open_app",
        )

    provider = PROVIDER_MAP.get(provider_name)
    if not provider:
        return AppActionResult(
            False,
            f"Không tìm thấy ứng dụng: {provider_name}",
            provider=provider_name,
        )

    try:
        result = await provider.execute(action, params)
        logger.info(
            "[APP_ROUTER] Executed: provider=%s action=%s success=%s",
            provider_name, action, result.success,
        )
        return result
    except Exception as e:
        logger.error("[APP_ROUTER] Error: %s", str(e)[:200])
        return AppActionResult(
            False,
            "Đã xảy ra lỗi khi thực hiện.",
            provider=provider_name,
        )


def get_all_capabilities() -> list[dict]:
    """Lấy danh sách toàn bộ apps và capabilities."""
    result = []
    for p in ALL_PROVIDERS:
        result.append({
            "name": p.name,
            "display_name": p.display_name,
            "icon": p.icon,
            "capabilities": p.get_capabilities(),
        })
    return result

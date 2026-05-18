"""
App Providers — AI Agent thực thi trực tiếp trên máy tính
===========================================================
KHÔNG chỉ trả URL — MỞ THẬT SỰ ứng dụng trên máy user.

Luồng:
  User: "mở cốc cốc" → Router parse → Provider execute
  → system_executor.open_app("coccoc") → subprocess.Popen()
  → Cốc Cốc mở trên desktop THẬT SỰ

Có GPS: Maps dùng lat/lng làm origin khi chỉ đường.
"""
from __future__ import annotations

import logging
import re
import urllib.parse
import urllib.request

from src.core.app_actions.base import AppProvider, AppActionResult
from src.core.app_actions.system_executor import (
    open_app, open_url_default_browser,
)

logger = logging.getLogger(__name__)


def _clean_youtube_query(query: str) -> tuple[str, bool]:
    """Remove command suffixes like 'rùi mở lên đi' from the actual search query."""
    play_first = bool(re.search(
        r"\b(?:rồi|roi|rùi|rui|và|va)?\s*(?:mở|mo|phát|phat|bật|bat|play|xem)\s+"
        r"(?:lên|luôn|luon|đi|di)\b",
        query,
        re.IGNORECASE,
    ))
    cleaned = re.sub(
        r"\s+\b(?:rồi|roi|rùi|rui|và|va)\s+"
        r"(?:mở|mo|phát|phat|bật|bat|play|xem)\s+"
        r"(?:lên|luôn|luon|đi|di)?\b.*$",
        "",
        query,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(
        r"\s+\b(?:mở|mo|phát|phat|bật|bat|play|xem)\s+"
        r"(?:lên|luôn|luon|đi|di)\b.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned or query.strip(), play_first


def _find_youtube_first_video_id(query: str) -> str | None:
    """Best-effort lookup of the first YouTube search result without extra dependencies."""
    search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
    req = urllib.request.Request(
        search_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
            ),
            "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        logger.warning("[YOUTUBE] First-result lookup failed: %s", str(exc)[:120])
        return None

    seen: set[str] = set()
    for pattern in (r'"videoId":"([A-Za-z0-9_-]{11})"', r"watch\?v=([A-Za-z0-9_-]{11})"):
        for video_id in re.findall(pattern, html):
            if video_id in seen:
                continue
            seen.add(video_id)
            return video_id
    return None


# ══════════════════════════════════════════════════════════════
# 1. Phone — Gọi điện
# ══════════════════════════════════════════════════════════════

class PhoneProvider(AppProvider):
    name = "phone"
    display_name = "Gọi điện"
    icon = "📞"

    def get_capabilities(self):
        return [
            {"action": "call", "description": "Gọi điện thoại", "example": "gọi cho 0901234567"},
        ]

    async def execute(self, action: str, params: dict) -> AppActionResult:
        phone = params.get("phone", "").strip()
        if not phone:
            return AppActionResult(False, "Vui lòng cho tôi số điện thoại.", provider=self.name)
        phone_clean = phone.replace(" ", "").replace("-", "").replace(".", "")
        # tel: hoạt động trên cả web + mobile
        return AppActionResult(
            True, f"Đang gọi cho {phone}...",
            intent_uri=f"tel:{phone_clean}",
            data={"web_url": f"tel:{phone_clean}"},
            provider=self.name, action="call",
        )


# ══════════════════════════════════════════════════════════════
# 2. SMS — Tin nhắn
# ══════════════════════════════════════════════════════════════

class SMSProvider(AppProvider):
    name = "sms"
    display_name = "Tin nhắn SMS"
    icon = "💬"

    def get_capabilities(self):
        return [
            {"action": "send_sms", "description": "Gửi tin nhắn SMS", "example": "nhắn tin cho 0901234567 nội dung em đã về"},
        ]

    async def execute(self, action: str, params: dict) -> AppActionResult:
        phone = params.get("phone", "").strip().replace(" ", "")
        body = params.get("body", "").strip()
        if not phone:
            return AppActionResult(False, "Vui lòng cho tôi số điện thoại.", provider=self.name)
        body_encoded = urllib.parse.quote(body) if body else ""
        uri = f"sms:{phone}?body={body_encoded}" if body else f"sms:{phone}"
        return AppActionResult(
            True,
            f"Đang mở tin nhắn tới {phone}" + (f" với nội dung: \"{body}\"" if body else ""),
            intent_uri=uri,
            data={"web_url": uri},  # sms: works on mobile browsers
            provider=self.name, action="send_sms",
        )


# ══════════════════════════════════════════════════════════════
# 3. Zalo
# ══════════════════════════════════════════════════════════════

class ZaloProvider(AppProvider):
    name = "zalo"
    display_name = "Zalo"
    icon = "💙"

    def get_capabilities(self):
        return [
            {"action": "open_zalo", "description": "Mở Zalo", "example": "mở zalo"},
            {"action": "zalo_chat", "description": "Nhắn tin Zalo", "example": "nhắn zalo cho 0901234567"},
        ]

    async def execute(self, action: str, params: dict) -> AppActionResult:
        phone = params.get("phone", "").strip().replace(" ", "")
        if action == "open_zalo":
            return AppActionResult(
                True, "Đang mở Zalo...",
                intent_uri="https://zalo.me",
                data={"web_url": "https://zalo.me"},
                provider=self.name, action="open_zalo",
            )
        elif action == "zalo_chat":
            if not phone:
                return AppActionResult(False, "Cho tôi số điện thoại Zalo.", provider=self.name)
            url = f"https://zalo.me/{phone}"
            return AppActionResult(
                True, f"Đang mở chat Zalo với {phone}...",
                intent_uri=url,
                data={"web_url": url},
                provider=self.name, action="zalo_chat",
            )
        return AppActionResult(False, "Không hỗ trợ.", provider=self.name)


# ══════════════════════════════════════════════════════════════
# 4. Facebook / Messenger
# ══════════════════════════════════════════════════════════════

class FacebookProvider(AppProvider):
    name = "facebook"
    display_name = "Facebook"
    icon = "📘"

    def get_capabilities(self):
        return [
            {"action": "open_fb", "description": "Mở Facebook", "example": "mở facebook"},
            {"action": "open_messenger", "description": "Mở Messenger", "example": "mở messenger"},
        ]

    async def execute(self, action: str, params: dict) -> AppActionResult:
        urls = {
            "open_fb": ("Đang mở Facebook...", "https://www.facebook.com"),
            "open_messenger": ("Đang mở Messenger...", "https://www.messenger.com"),
        }
        if action in urls:
            msg, url = urls[action]
            return AppActionResult(
                True, msg,
                intent_uri=url,
                data={"web_url": url},
                provider=self.name, action=action,
            )
        return AppActionResult(False, "Không hỗ trợ.", provider=self.name)


# ══════════════════════════════════════════════════════════════
# 5. YouTube — Tìm + bật video
# ══════════════════════════════════════════════════════════════

class YouTubeProvider(AppProvider):
    name = "youtube"
    display_name = "YouTube"
    icon = "📺"

    def get_capabilities(self):
        return [
            {"action": "open_youtube", "description": "Mở YouTube", "example": "mở youtube"},
            {"action": "youtube_search", "description": "Tìm video YouTube", "example": "youtube kiếm bài sóng gió"},
        ]

    async def execute(self, action: str, params: dict) -> AppActionResult:
        query, query_wants_play = _clean_youtube_query(params.get("query", "").strip())
        play_first = bool(params.get("play_first")) or query_wants_play
        if action == "open_youtube":
            url = "https://www.youtube.com"
            ok, msg = open_url_default_browser(url)
            return AppActionResult(
                ok, "Đã mở YouTube trên trình duyệt mặc định." if ok else msg,
                data={"executed_on_server": True},
                provider=self.name, action="open_youtube",
            )
        elif action == "youtube_search":
            if not query:
                return AppActionResult(False, "Bạn muốn tìm video gì?", provider=self.name)
            if play_first:
                video_id = _find_youtube_first_video_id(query)
                if video_id:
                    url = f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
                    ok, msg = open_url_default_browser(url)
                    return AppActionResult(
                        ok,
                        f"Đã mở video đầu tiên cho \"{query}\"." if ok else msg,
                        data={"executed_on_server": True, "video_id": video_id},
                        provider=self.name, action="youtube_search",
                    )

            q = urllib.parse.quote(query)
            url = f"https://www.youtube.com/results?search_query={q}"
            ok, msg = open_url_default_browser(url)
            return AppActionResult(
                ok,
                f"Đã mở YouTube và tìm \"{query}\" trên trình duyệt mặc định." if ok else msg,
                data={"executed_on_server": True},
                provider=self.name, action="youtube_search",
            )
        return AppActionResult(False, "Không hỗ trợ.", provider=self.name)


# ══════════════════════════════════════════════════════════════
# 6. Google Maps — web URL thay vì geo: URI
# ══════════════════════════════════════════════════════════════

class MapsProvider(AppProvider):
    name = "maps"
    display_name = "Google Maps"
    icon = "🗺️"

    def get_capabilities(self):
        return [
            {"action": "open_maps", "description": "Mở Maps", "example": "mở bản đồ"},
            {"action": "search_place", "description": "Tìm địa điểm", "example": "tìm quán cà phê gần đây"},
            {"action": "navigate", "description": "Chỉ đường", "example": "chỉ đường đến sân bay Tân Sơn Nhất"},
        ]

    async def execute(self, action: str, params: dict) -> AppActionResult:
        query = params.get("query", "").strip()
        destination = params.get("destination", query).strip()
        loc = params.get("_location")  # GPS từ frontend

        if action == "open_maps":
            url = "https://www.google.com/maps"
            if loc:
                url = f"https://www.google.com/maps/@{loc['lat']},{loc['lng']},15z"
            ok, _ = open_url_default_browser(url)
            return AppActionResult(
                ok, "Đã mở Google Maps trên trình duyệt mặc định.",
                data={"executed_on_server": True},
                provider=self.name, action="open_maps",
            )
        elif action == "search_place":
            if not query:
                return AppActionResult(False, "Bạn muốn tìm gì trên bản đồ?", provider=self.name)
            q = urllib.parse.quote(query)
            url = f"https://www.google.com/maps/search/{q}"
            if loc:
                url += f"/@{loc['lat']},{loc['lng']},14z"
            ok, _ = open_url_default_browser(url)
            return AppActionResult(
                ok, f"Đã mở Google Maps và tìm \"{query}\".",
                data={"executed_on_server": True},
                provider=self.name, action="search_place",
            )
        elif action == "navigate":
            if not destination:
                return AppActionResult(False, "Bạn muốn đi đến đâu?", provider=self.name)
            d = urllib.parse.quote(destination)
            url = f"https://www.google.com/maps/dir/?api=1&destination={d}"
            if loc:
                url += f"&origin={loc['lat']},{loc['lng']}"
                msg = f"Đã mở Google Maps chỉ đường từ vị trí hiện tại đến \"{destination}\"."
            else:
                msg = f"Đã mở Google Maps chỉ đường đến \"{destination}\"."
            ok, _ = open_url_default_browser(url)
            return AppActionResult(
                ok, msg,
                data={"executed_on_server": True},
                provider=self.name, action="navigate",
            )
        return AppActionResult(False, "Không hỗ trợ.", provider=self.name)


# ══════════════════════════════════════════════════════════════
# 7. Gmail
# ══════════════════════════════════════════════════════════════

class GmailProvider(AppProvider):
    name = "gmail"
    display_name = "Gmail"
    icon = "📧"

    def get_capabilities(self):
        return [
            {"action": "open_gmail", "description": "Mở Gmail", "example": "mở email"},
            {"action": "send_email", "description": "Gửi email", "example": "gửi email cho abc@gmail.com"},
        ]

    async def execute(self, action: str, params: dict) -> AppActionResult:
        to = params.get("to", "").strip()
        subject = params.get("subject", "").strip()
        body = params.get("body", "").strip()

        if action == "open_gmail":
            url = "https://mail.google.com"
            return AppActionResult(
                True, "Đang mở Gmail...",
                intent_uri=url, data={"web_url": url},
                provider=self.name, action="open_gmail",
            )
        elif action == "send_email":
            # mailto: works on all platforms
            parts = [f"mailto:{to}"]
            qp = []
            if subject:
                qp.append(f"subject={urllib.parse.quote(subject)}")
            if body:
                qp.append(f"body={urllib.parse.quote(body)}")
            if qp:
                parts[0] += "?" + "&".join(qp)
            # Web fallback: Gmail compose
            web_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={urllib.parse.quote(to)}"
            if subject:
                web_url += f"&su={urllib.parse.quote(subject)}"
            if body:
                web_url += f"&body={urllib.parse.quote(body)}"
            return AppActionResult(
                True, f"Đang soạn email" + (f" tới {to}" if to else "") + "...",
                intent_uri=parts[0], data={"web_url": web_url},
                provider=self.name, action="send_email",
            )
        return AppActionResult(False, "Không hỗ trợ.", provider=self.name)


# ══════════════════════════════════════════════════════════════
# 8. Camera — mở app Camera Windows
# ══════════════════════════════════════════════════════════════

class CameraProvider(AppProvider):
    name = "camera"
    display_name = "Camera"
    icon = "📷"

    def get_capabilities(self):
        return [
            {"action": "open_camera", "description": "Mở camera", "example": "mở camera"},
        ]

    async def execute(self, action: str, params: dict) -> AppActionResult:
        ok, msg = open_app("camera")
        return AppActionResult(
            ok, "Đã mở Camera trên máy tính." if ok else msg,
            data={"executed_on_server": True},
            provider=self.name, action=action,
        )


# ══════════════════════════════════════════════════════════════
# 9. Web Browser — Mở website / tìm kiếm
# ══════════════════════════════════════════════════════════════

class WebBrowserProvider(AppProvider):
    name = "web"
    display_name = "Trình duyệt"
    icon = "🌐"

    def get_capabilities(self):
        return [
            {"action": "open_url", "description": "Mở trang web", "example": "mở trang google.com"},
            {"action": "web_search", "description": "Tìm kiếm Google", "example": "tìm kiếm thời tiết hôm nay"},
        ]

    async def execute(self, action: str, params: dict) -> AppActionResult:
        url = params.get("url", "").strip()
        query = params.get("query", "").strip()

        if action == "open_url":
            if not url:
                return AppActionResult(False, "Bạn muốn mở trang web nào?", provider=self.name)
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            ok, msg = open_url_default_browser(url)
            return AppActionResult(
                ok, f"Đã mở {url} trên trình duyệt mặc định." if ok else msg,
                data={"executed_on_server": True},
                provider=self.name, action="open_url",
            )
        elif action == "web_search":
            if not query:
                return AppActionResult(False, "Bạn muốn tìm gì?", provider=self.name)
            q = urllib.parse.quote(query)
            url = f"https://www.google.com/search?q={q}"
            ok, msg = open_url_default_browser(url)
            return AppActionResult(
                ok, f"Đã tìm kiếm \"{query}\" trên Google." if ok else msg,
                data={"executed_on_server": True},
                provider=self.name, action="web_search",
            )
        return AppActionResult(False, "Không hỗ trợ.", provider=self.name)


# ══════════════════════════════════════════════════════════════
# 10. TikTok
# ══════════════════════════════════════════════════════════════

class TikTokProvider(AppProvider):
    name = "tiktok"
    display_name = "TikTok"
    icon = "🎵"

    def get_capabilities(self):
        return [
            {"action": "open_tiktok", "description": "Mở TikTok", "example": "mở tiktok"},
        ]

    async def execute(self, action: str, params: dict) -> AppActionResult:
        url = "https://www.tiktok.com"
        ok, _ = open_url_default_browser(url)
        return AppActionResult(
            ok, "Đã mở TikTok trên trình duyệt mặc định.",
            data={"executed_on_server": True},
            provider=self.name, action="open_tiktok",
        )


# ══════════════════════════════════════════════════════════════
# 11. Spotify
# ══════════════════════════════════════════════════════════════

class SpotifyProvider(AppProvider):
    name = "spotify"
    display_name = "Spotify"
    icon = "🎧"

    def get_capabilities(self):
        return [
            {"action": "open_spotify", "description": "Mở Spotify", "example": "mở spotify"},
            {"action": "spotify_search", "description": "Tìm bài hát", "example": "spotify nghe bài hạ còn vương nắng"},
        ]

    async def execute(self, action: str, params: dict) -> AppActionResult:
        query = params.get("query", "").strip()
        if action == "open_spotify":
            # Thử mở app Spotify trước, nếu không có → web
            ok, msg = open_app("spotify")
            if not ok:
                ok, _ = open_url_default_browser("https://open.spotify.com")
                msg = "Đã mở Spotify Web." if ok else msg
            else:
                msg = "Đã mở app Spotify."
            return AppActionResult(ok, msg, data={"executed_on_server": True}, provider=self.name, action="open_spotify")
        elif action == "spotify_search":
            if not query:
                return await self.execute("open_spotify", params)
            q = urllib.parse.quote(query)
            url = f"https://open.spotify.com/search/{q}"
            ok, _ = open_url_default_browser(url)
            return AppActionResult(
                ok, f"Đã tìm \"{query}\" trên Spotify." if ok else "Không thể mở Spotify.",
                data={"executed_on_server": True},
                provider=self.name, action="spotify_search",
            )
        return AppActionResult(False, "Không hỗ trợ.", provider=self.name)


# ══════════════════════════════════════════════════════════════
# 12. Cốc Cốc — Trình duyệt Việt Nam
# ══════════════════════════════════════════════════════════════

class CocCocProvider(AppProvider):
    name = "coccoc"
    display_name = "Cốc Cốc"
    icon = "🟢"

    def get_capabilities(self):
        return [
            {"action": "open_coccoc", "description": "Mở Cốc Cốc", "example": "mở cốc cốc"},
            {"action": "coccoc_search", "description": "Tìm trên Cốc Cốc", "example": "cốc cốc tìm thời tiết"},
        ]

    async def execute(self, action: str, params: dict) -> AppActionResult:
        query = params.get("query", "").strip()
        if action == "open_coccoc":
            # Mở app Cốc Cốc THẬT SỰ trên desktop
            ok, msg = open_app("coccoc")
            if not ok:
                ok, _ = open_url_default_browser("https://coccoc.com")
                msg = "Đã mở trang Cốc Cốc trên trình duyệt mặc định." if ok else msg
            else:
                msg = "Đã mở trình duyệt Cốc Cốc."
            return AppActionResult(
                ok, msg,
                data={"executed_on_server": True},
                provider=self.name, action="open_coccoc",
            )
        elif action == "coccoc_search":
            q = urllib.parse.quote(query) if query else ""
            url = f"https://coccoc.com/search#query={q}" if q else "https://coccoc.com"
            ok, _ = open_url_default_browser(url)
            return AppActionResult(
                ok, f"Đã tìm \"{query}\" trên Cốc Cốc." if query else "Đã mở Cốc Cốc.",
                data={"executed_on_server": True},
                provider=self.name, action="coccoc_search",
            )
        return AppActionResult(False, "Không hỗ trợ.", provider=self.name)


# ══════════════════════════════════════════════════════════════
# 13. Alarm — Đặt báo thức + mở đồng hồ
# ══════════════════════════════════════════════════════════════
import re as _re_alarm


def _parse_vietnamese_time(text: str) -> tuple[int, int] | None:
    """
    Parse chuỗi thời gian tiếng Việt → (hour_24, minute).

    Ví dụ:
        "2h sáng"        → (2, 0)
        "5h30 sáng"      → (5, 30)
        "5:30 chiều"     → (17, 30)
        "14:00"          → (14, 0)
        "12 giờ trưa"    → (12, 0)
        "2 giờ đêm"      → (2, 0)   # giữ nguyên (đêm = sáng sớm khi < 12)
        "12h khuya"      → (0, 0)   # 12 khuya = 00:00

    Returns: tuple (hour, minute) hoặc None nếu không parse được.
    """
    text = text.lower().strip()

    # Pattern 1: 2h, 5h30, 14:00, 5 giờ, 5:30
    m = _re_alarm.search(
        r"(?P<hour>\d{1,2})\s*(?:h|giờ|gio|:)\s*(?P<minute>\d{1,2})?\s*"
        r"(?P<period>sáng|sang|chiều|chieu|tối|toi|trưa|trua|đêm|dem|khuya|am|pm)?",
        text,
    )
    if not m:
        # Pattern 2: "5 sáng", "5 chiều" (không có h/giờ/colon)
        m = _re_alarm.search(
            r"(?P<hour>\d{1,2})\s+"
            r"(?P<period>sáng|sang|chiều|chieu|tối|toi|trưa|trua|đêm|dem|khuya|am|pm)",
            text,
        )
        if not m:
            return None

    try:
        hour = int(m.group("hour"))
    except (ValueError, IndexError, TypeError):
        return None

    minute_str = m.groupdict().get("minute")
    minute = int(minute_str) if minute_str else 0

    if hour > 23 or minute > 59:
        return None

    period = (m.groupdict().get("period") or "").lower()

    # Convert sang 24h format
    if period in ("chiều", "chieu", "tối", "toi", "pm"):
        # 1-11 chiều/tối → +12; 12 chiều = 12 (giữ); 12 tối = 0 (nửa đêm)
        if 1 <= hour <= 11:
            hour += 12
    elif period in ("sáng", "sang", "am"):
        if hour == 12:
            hour = 0  # 12 sáng = 00:00 (nửa đêm)
    elif period == "khuya":
        # 12 khuya = 00:00, 1-3 khuya = 01-03
        if hour == 12:
            hour = 0
    elif period in ("đêm", "dem"):
        # Tương tự khuya: thường < 12
        if hour == 12:
            hour = 0
    # "trưa" giữ nguyên (11-13)

    if hour > 23:
        return None
    return hour, minute


class AlarmProvider(AppProvider):
    """
    Báo thức + Đồng hồ.

    Trên Android (APK Capacitor): fire intent ACTION_SET_ALARM với extras
    (HOUR, MINUTES, MESSAGE) → Clock app tự cài báo thức.

    Trên Web/Desktop: fallback URL Google search "set alarm HH:MM" hoặc
    open `ms-clock:` (Windows). Frontend tự chọn fallback dựa vào platform.
    """
    name = "alarm"
    display_name = "Báo thức"
    icon = "⏰"

    def get_capabilities(self):
        return [
            {
                "action": "set_alarm",
                "description": "Đặt báo thức theo giờ",
                "example": "đặt báo thức 6h sáng",
            },
            {
                "action": "open_clock",
                "description": "Mở đồng hồ / xem báo thức hiện có",
                "example": "mở đồng hồ",
            },
        ]

    async def execute(self, action: str, params: dict) -> AppActionResult:
        if action == "open_clock":
            return AppActionResult(
                True,
                "Đang mở đồng hồ...",
                intent_uri="https://www.google.com/search?q=alarm",
                data={
                    "android_intent": {
                        "action": "android.intent.action.SHOW_ALARMS",
                    },
                    "web_url": "https://www.google.com/search?q=alarm",
                    "requires_native": True,
                },
                provider=self.name,
                action="open_clock",
            )

        # ── set_alarm ──
        time_text = params.get("time", "").strip()
        message = params.get("message", "").strip() or "Báo thức"

        parsed = _parse_vietnamese_time(time_text) if time_text else None
        if parsed is None:
            return AppActionResult(
                False,
                "Cho tôi biết giờ báo thức (vd: 6h sáng, 5h30 chiều, 14:00).",
                provider=self.name,
                action="set_alarm",
            )

        hour, minute = parsed
        time_display = f"{hour:02d}:{minute:02d}"

        # Web fallback: Google "set alarm 6:00 am"
        period_url = "am" if hour < 12 else "pm"
        display_hour = hour if 1 <= hour <= 12 else (hour - 12 if hour > 12 else 12)
        web_url = (
            f"https://www.google.com/search?q=set+alarm+"
            f"{display_hour}%3A{minute:02d}+{period_url}"
        )

        return AppActionResult(
            True,
            f"Đã đặt báo thức lúc {time_display}.",
            intent_uri=web_url,
            data={
                # Trên Android: frontend Capacitor sẽ fire intent này
                "android_intent": {
                    "action": "android.intent.action.SET_ALARM",
                    "extras": {
                        "android.intent.extra.alarm.HOUR": hour,
                        "android.intent.extra.alarm.MINUTES": minute,
                        "android.intent.extra.alarm.MESSAGE": message,
                        # SKIP_UI=False → user xác nhận trong Clock app, an toàn
                        "android.intent.extra.alarm.SKIP_UI": False,
                    },
                },
                "web_url": web_url,
                "requires_native": True,
                "alarm_time": time_display,
                "alarm_message": message,
            },
            provider=self.name,
            action="set_alarm",
        )


# ══════════════════════════════════════════════════════════════
# Provider Registry
# ══════════════════════════════════════════════════════════════

ALL_PROVIDERS: list[AppProvider] = [
    PhoneProvider(),
    SMSProvider(),
    ZaloProvider(),
    FacebookProvider(),
    YouTubeProvider(),
    MapsProvider(),
    GmailProvider(),
    CameraProvider(),
    WebBrowserProvider(),
    TikTokProvider(),
    SpotifyProvider(),
    CocCocProvider(),
    AlarmProvider(),
]

PROVIDER_MAP: dict[str, AppProvider] = {p.name: p for p in ALL_PROVIDERS}

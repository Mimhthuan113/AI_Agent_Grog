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
import urllib.parse

from src.core.app_actions.base import AppProvider, AppActionResult
from src.core.app_actions.system_executor import (
    open_app, open_url_default_browser, open_explorer,
    resolve_app_name, KNOWN_APPS,
)

logger = logging.getLogger(__name__)


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
        query = params.get("query", "").strip()
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
]

PROVIDER_MAP: dict[str, AppProvider] = {p.name: p for p in ALL_PROVIDERS}

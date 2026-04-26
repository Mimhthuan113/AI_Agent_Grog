"""
Home Assistant Client — REST API kết nối thật
================================================
Async client gọi Home Assistant REST API.
Hỗ trợ:
- Service call (turn_on/turn_off/set_brightness/...)
- Get entity state
- Health check (ping)
- Retry với exponential backoff cho lỗi tạm thời
- Graceful degradation: nếu HA down → trả lỗi rõ, không crash

Action mapping:
  turn_on / turn_off    → <domain>.turn_on / turn_off
  set_brightness         → light.turn_on (brightness param)
  set_color_temp         → light.turn_on (color_temp param)
  set_temperature        → climate.set_temperature
  set_hvac_mode          → climate.set_hvac_mode
  lock / unlock          → lock.lock / unlock
  get_state              → GET /api/states/<entity_id>

Reference:
  https://developers.home-assistant.io/docs/api/rest/
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)


# ── Action → Service Mapping ───────────────────────────────

# Map action string → (domain_override, service_name, extra_params_keys)
# domain_override = None → dùng domain từ entity_id (light.x → "light")
_ACTION_MAP: dict[str, tuple[str | None, str, list[str]]] = {
    # Phổ thông
    "turn_on": (None, "turn_on", []),
    "turn_off": (None, "turn_off", []),
    "toggle": (None, "toggle", []),
    # Light
    "set_brightness": ("light", "turn_on", ["brightness", "brightness_pct"]),
    "set_color_temp": ("light", "turn_on", ["color_temp", "kelvin"]),
    "set_color": ("light", "turn_on", ["rgb_color", "hs_color", "xy_color"]),
    # Lock
    "lock": ("lock", "lock", []),
    "unlock": ("lock", "unlock", []),
    # Climate / điều hoà
    "set_temperature": ("climate", "set_temperature", ["temperature", "target_temp_high", "target_temp_low"]),
    "set_hvac_mode": ("climate", "set_hvac_mode", ["hvac_mode"]),
    "set_fan_mode": ("climate", "set_fan_mode", ["fan_mode"]),
    "set_humidity": ("climate", "set_humidity", ["humidity"]),
    # Fan
    "set_speed": ("fan", "set_percentage", ["percentage"]),
    "set_preset_mode": ("fan", "set_preset_mode", ["preset_mode"]),
    # Cover (rèm, cửa cuốn)
    "open_cover": ("cover", "open_cover", []),
    "close_cover": ("cover", "close_cover", []),
    "set_cover_position": ("cover", "set_cover_position", ["position"]),
    # Media player
    "play": ("media_player", "media_play", []),
    "pause": ("media_player", "media_pause", []),
    "stop": ("media_player", "media_stop", []),
    "set_volume": ("media_player", "volume_set", ["volume_level"]),
    # Generic helpers
    "set_value": (None, "set_value", ["value"]),  # input_number, input_text
    "select_option": (None, "select_option", ["option"]),  # input_select, select
}


class HAClientError(Exception):
    """Lỗi giao tiếp Home Assistant."""


class HAClient:
    """
    Async Home Assistant REST client.
    Sử dụng httpx.AsyncClient với connection pooling.
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 5.0,
        verify_ssl: bool = False,
        max_retries: int = 2,
    ):
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._max_retries = max_retries

        self._http: httpx.AsyncClient | None = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            verify=verify_ssl,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "AishaAgent/1.0",
            },
        )

    # ── Public API ─────────────────────────────────────────

    async def ping(self) -> bool:
        """Ping endpoint /api/ để kiểm tra HA online + token đúng."""
        try:
            resp = await self._http.get("/api/")
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning("[HA] Ping failed: %s", str(e)[:120])
            return False

    async def call_service(
        self,
        entity_id: str,
        action: str,
        params: dict | None = None,
    ) -> dict:
        """
        Gọi 1 service trên Home Assistant.

        Args:
            entity_id: Ví dụ "light.phong_ngu", "lock.cua_chinh"
            action:    Ví dụ "turn_on", "set_brightness", "lock"
            params:    Param phụ ví dụ {"brightness": 200, "temperature": 25}

        Returns:
            Dict response từ HA: {"entity_id", "state", "attributes"}.

        Raises:
            HAClientError nếu HA reject lệnh hoặc network error.
        """
        params = params or {}
        domain, service, extra_keys = self._resolve_service(entity_id, action)

        # Build payload
        payload: dict[str, Any] = {"entity_id": entity_id}
        for k in extra_keys:
            if k in params and params[k] is not None:
                payload[k] = params[k]

        url = f"/api/services/{domain}/{service}"
        logger.info(
            "[HA] CALL: %s entity=%s payload_keys=%s",
            url, entity_id, list(payload.keys()),
        )

        last_err: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = await self._http.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()  # HA trả về list states đã thay đổi
                logger.info("[HA] OK: %s → %d entities updated", entity_id, len(data) if isinstance(data, list) else 0)
                return {
                    "entity_id": entity_id,
                    "domain": domain,
                    "service": service,
                    "updated": data,
                }
            except httpx.HTTPStatusError as e:
                # 4xx → lỗi user, không retry
                if 400 <= e.response.status_code < 500:
                    body = e.response.text[:200]
                    logger.error("[HA] HTTP %d: %s", e.response.status_code, body)
                    raise HAClientError(f"HA rejected: HTTP {e.response.status_code}") from e
                last_err = e
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
                last_err = e
                logger.warning(
                    "[HA] Network error (attempt %d/%d): %s",
                    attempt + 1, self._max_retries + 1, str(e)[:120],
                )

            # Exponential backoff: 0.3s, 0.6s, 1.2s
            if attempt < self._max_retries:
                await asyncio.sleep(0.3 * (2 ** attempt))

        raise HAClientError(f"HA unreachable after {self._max_retries + 1} attempts: {last_err}")

    async def get_state(self, entity_id: str) -> dict | None:
        """Lấy trạng thái hiện tại của 1 entity."""
        url = f"/api/states/{entity_id}"
        try:
            resp = await self._http.get(url)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("[HA] get_state(%s) failed: %s", entity_id, str(e)[:120])
            return None

    async def list_entities(self, domain_filter: str | None = None) -> list[dict]:
        """Danh sách tất cả entity trong HA, optional filter theo domain."""
        try:
            resp = await self._http.get("/api/states")
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list):
                return []
            if domain_filter:
                data = [e for e in data if e.get("entity_id", "").startswith(f"{domain_filter}.")]
            return data
        except Exception as e:
            logger.warning("[HA] list_entities failed: %s", str(e)[:120])
            return []

    async def close(self) -> None:
        """Đóng connection pool."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None
            logger.info("[HA] Client closed")

    # ── Internal ───────────────────────────────────────────

    @staticmethod
    def _resolve_service(entity_id: str, action: str) -> tuple[str, str, list[str]]:
        """
        Map (entity_id, action) → (domain, service, extra_param_keys).

        Ví dụ:
          ("light.bedroom", "turn_on") → ("light", "turn_on", [])
          ("light.bedroom", "set_brightness") → ("light", "turn_on", ["brightness"])
          ("lock.cua", "lock") → ("lock", "lock", [])
        """
        # Domain từ entity_id: "light.bedroom" → "light"
        try:
            entity_domain = entity_id.split(".", 1)[0].lower()
        except Exception:
            entity_domain = "homeassistant"

        mapping = _ACTION_MAP.get(action)
        if mapping is None:
            # Fallback: thử dùng action làm tên service trực tiếp
            return entity_domain, action, []

        domain_override, service, extra_keys = mapping
        domain = domain_override or entity_domain
        return domain, service, extra_keys


# ── Singleton (lifespan-managed) ───────────────────────────

_ha_client: HAClient | None = None


async def get_ha_client() -> HAClient:
    """
    Lazy-init HA client singleton. Gọi ở lifespan startup.
    Raise HAClientError nếu ping fail (caller có thể catch để fallback mock).
    """
    global _ha_client
    if _ha_client is None:
        settings = get_settings()
        _ha_client = HAClient(
            base_url=settings.ha_base_url,
            token=settings.ha_token,
            timeout=float(settings.ha_timeout),
            verify_ssl=settings.ha_verify_ssl,
        )
        if not await _ha_client.ping():
            await _ha_client.close()
            _ha_client = None
            raise HAClientError(
                f"Cannot connect to HA at {settings.ha_base_url}"
            )
    return _ha_client


async def close_ha_client() -> None:
    """Đóng client ở lifespan shutdown."""
    global _ha_client
    if _ha_client is not None:
        await _ha_client.close()
        _ha_client = None

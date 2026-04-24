"""
Geocoder — Dịch tọa độ GPS → Địa chỉ tiếng Việt
====================================================
Chiến lược 2 tầng:
  1. Google Geocoding API (chính xác nhất, miễn phí 28K req/tháng)
  2. Nominatim / OpenStreetMap (miễn phí không giới hạn, kém chi tiết hơn)
  3. Fallback: trả tọa độ thô

Tính năng:
- Cache kết quả 5 phút (tránh spam API)
- Timeout 3s (không chặn luồng chính)
- Graceful degradation: lỗi → tầng tiếp theo
"""
from __future__ import annotations

import os
import time
import json
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass

from src.config import get_settings

logger = logging.getLogger(__name__)

# ── Cache ──────────────────────────────────────────────────
_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 300  # 5 phút
_CACHE_RADIUS_METERS = 50


@dataclass
class GeoResult:
    """Kết quả Reverse Geocoding."""
    address: str          # Địa chỉ đầy đủ tiếng Việt
    district: str = ""    # Quận / Huyện
    city: str = ""        # Thành phố / Tỉnh
    country: str = ""     # Quốc gia
    lat: float = 0.0
    lng: float = 0.0
    source: str = ""      # "google" | "nominatim" | "fallback"
    raw: dict | None = None


def _haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Tính khoảng cách giữa 2 tọa độ (đơn vị mét)."""
    import math
    R = 6_371_000
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _check_cache(lat: float, lng: float) -> str | None:
    """Kiểm tra cache — nếu gần vị trí cũ thì dùng lại."""
    now = time.time()
    for key, (address, ts) in list(_cache.items()):
        if now - ts > _CACHE_TTL:
            del _cache[key]
            continue
        clat, clng = map(float, key.split(","))
        if _haversine_meters(lat, lng, clat, clng) < _CACHE_RADIUS_METERS:
            return address
    return None


def _save_cache(lat: float, lng: float, address: str):
    """Lưu kết quả vào cache."""
    _cache[f"{lat},{lng}"] = (address, time.time())


# ══════════════════════════════════════════════════════════════
# Tầng 1: Google Geocoding API (chính xác nhất)
# ══════════════════════════════════════════════════════════════

def _google_reverse(lat: float, lng: float, timeout: float = 3.0) -> GeoResult | None:
    """
    Google Geocoding API — chính xác cấp số nhà.
    Cần GOOGLE_MAPS_API_KEY trong .env
    Miễn phí: $200 credit/tháng ≈ 28,000 requests
    """
    settings = get_settings()
    api_key = settings.google_maps_api_key
    if not api_key:
        return None

    url = (
        f"https://maps.googleapis.com/maps/api/geocode/json"
        f"?latlng={lat},{lng}&language=vi&key={api_key}"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AishaAgent/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("status") != "OK" or not data.get("results"):
            err_msg = data.get("error_message", "Không có chi tiết")
            logger.warning("[GEO:Google] Status: %s — %s", data.get("status"), err_msg)
            print(f"[GEO:Google] ❌ {data.get('status')}: {err_msg}")
            return None

        # Lấy kết quả đầu tiên (chính xác nhất)
        result = data["results"][0]
        address = result.get("formatted_address", "")

        # Parse components
        components = {c["types"][0]: c["long_name"]
                      for c in result.get("address_components", [])
                      if c.get("types")}

        district = (
            components.get("administrative_area_level_2", "") or
            components.get("sublocality_level_1", "")
        )
        city = (
            components.get("administrative_area_level_1", "") or
            components.get("locality", "")
        )

        # Bỏ ", Việt Nam" thừa cuối chuỗi cho gọn
        if address.endswith(", Việt Nam"):
            address = address[:-len(", Việt Nam")]
        elif address.endswith(", Vietnam"):
            address = address[:-len(", Vietnam")]

        logger.info("[GEO:Google] (%.4f,%.4f) → %s", lat, lng, address[:80])

        return GeoResult(
            address=address,
            district=district,
            city=city,
            country="Việt Nam",
            lat=lat, lng=lng,
            source="google",
            raw=components,
        )

    except Exception as e:
        logger.warning("[GEO:Google] Error: %s", str(e)[:100])
        return None


# ══════════════════════════════════════════════════════════════
# Tầng 2: Nominatim / OpenStreetMap (miễn phí vĩnh viễn)
# ══════════════════════════════════════════════════════════════

def _nominatim_reverse(lat: float, lng: float, timeout: float = 3.0) -> GeoResult | None:
    """
    Nominatim (OpenStreetMap) — miễn phí, không cần key.
    Kém chi tiết hơn Google ở VN nhưng luôn available.
    """
    url = (
        f"https://nominatim.openstreetmap.org/reverse"
        f"?lat={lat}&lon={lng}&format=json&addressdetails=1"
        f"&accept-language=vi&zoom=19&extratags=1"
    )

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "AishaSmartHomeAgent/1.0 (contact: dev@aisha.local)",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        display_name = data.get("display_name", "")
        addr = data.get("address", {})

        # Xây dựng địa chỉ — ưu tiên đầy đủ nhất có thể
        parts = []
        house = addr.get("house_number", "")
        road = addr.get("road", "")
        if house:
            parts.append(house)
        if road:
            parts.append(road)

        # Khu vực
        suburb = (
            addr.get("neighbourhood", "") or
            addr.get("quarter", "") or
            addr.get("suburb", "")
        )
        if suburb:
            parts.append(suburb)

        # Phường/Xã
        ward = addr.get("village", "") or addr.get("hamlet", "")
        if ward and ward != suburb:
            parts.append(ward)

        # Quận/Huyện
        district = (
            addr.get("city_district", "") or
            addr.get("district", "") or
            addr.get("county", "")
        )
        if district:
            parts.append(district)

        # Thành phố
        city = addr.get("city", "") or addr.get("town", "") or addr.get("state", "")
        if city:
            parts.append(city)

        # Nếu quá ít info → dùng display_name gốc (bỏ ", Việt Nam" cuối)
        if len(parts) < 2:
            address = display_name
            if address.endswith(", Việt Nam"):
                address = address[:-len(", Việt Nam")]
        else:
            address = ", ".join(parts)

        logger.info("[GEO:Nominatim] (%.4f,%.4f) → %s", lat, lng, address[:80])

        return GeoResult(
            address=address,
            district=district,
            city=city,
            country=addr.get("country", ""),
            lat=lat, lng=lng,
            source="nominatim",
            raw=addr,
        )

    except Exception as e:
        logger.warning("[GEO:Nominatim] Error: %s", str(e)[:100])
        return None


# ══════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════

def reverse_geocode(lat: float, lng: float, timeout: float = 3.0) -> GeoResult:
    """
    Dịch tọa độ GPS → địa chỉ tiếng Việt.

    Chiến lược (waterfall):
      1. Cache (nếu gần vị trí cũ < 50m)
      2. Google Geocoding API (nếu có key)
      3. Nominatim / OpenStreetMap
      4. Fallback: tọa độ thô
    """
    # 1. Cache
    cached = _check_cache(lat, lng)
    if cached:
        logger.debug("[GEO] Cache hit: %s", cached[:60])
        return GeoResult(address=cached, lat=lat, lng=lng, source="cache")

    # 2. Google (chính xác nhất)
    result = _google_reverse(lat, lng, timeout)
    if result:
        _save_cache(lat, lng, result.address)
        return result

    # 3. Nominatim (fallback miễn phí)
    result = _nominatim_reverse(lat, lng, timeout)
    if result:
        _save_cache(lat, lng, result.address)
        return result

    # 4. Fallback
    fallback = f"Tọa độ: {lat:.5f}, {lng:.5f}"
    return GeoResult(address=fallback, lat=lat, lng=lng, source="fallback")


def format_location_context(lat: float, lng: float) -> str:
    """
    Tạo context string ngắn gọn để inject vào System Prompt LLM.

    Ví dụ: "Người dùng đang ở: 62 NVC nối dài, Ninh Kiều, Cần Thơ (via Google)"
    """
    geo = reverse_geocode(lat, lng)
    return f"Người dùng đang ở: {geo.address}"


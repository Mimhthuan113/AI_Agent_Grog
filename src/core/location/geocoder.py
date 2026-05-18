"""
Geocoder — Dịch tọa độ GPS → Địa chỉ tiếng Việt
====================================================
Dùng Nominatim (OpenStreetMap) — hoàn toàn miễn phí, không cần API key.

Tính năng:
- Reverse geocode: (lat, lng) → "62 KV4 NVC nối dài, Ninh Kiều, Cần Thơ"
- Cache kết quả 5 phút (tránh spam API)
- Timeout 3s (không chặn luồng chính)
- Graceful degradation: lỗi → trả tọa độ thô
"""
from __future__ import annotations

import time
import json
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── Cache ──────────────────────────────────────────────────
_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 300  # 5 phút

# Radius (meter) — nếu tọa độ mới cách tọa độ cache < radius → dùng cache
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
    raw: dict | None = None  # Raw response từ Nominatim


def _haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Tính khoảng cách giữa 2 tọa độ (đơn vị mét)."""
    import math
    R = 6_371_000  # Bán kính trái đất (mét)
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


def reverse_geocode(lat: float, lng: float, timeout: float = 3.0) -> GeoResult:
    """
    Dịch tọa độ GPS → địa chỉ tiếng Việt.
    
    Dùng Nominatim (OpenStreetMap) — MIỄN PHÍ, không cần key.
    
    Args:
        lat: Latitude (vĩ độ)
        lng: Longitude (kinh độ)
        timeout: Timeout (giây)
        
    Returns:
        GeoResult với địa chỉ đầy đủ
    """
    # Check cache trước
    cached = _check_cache(lat, lng)
    if cached:
        logger.debug("[GEO] Cache hit: %s", cached[:60])
        return GeoResult(address=cached, lat=lat, lng=lng)

    url = (
        f"https://nominatim.openstreetmap.org/reverse"
        f"?lat={lat}&lon={lng}&format=json&addressdetails=1"
        f"&accept-language=vi&zoom=18"
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

        # Xây dựng địa chỉ ngắn gọn hơn display_name
        parts = []
        # Số nhà + đường
        house = addr.get("house_number", "")
        road = addr.get("road", "")
        if house:
            parts.append(house)
        if road:
            parts.append(road)

        # Khu vực / Phường
        suburb = addr.get("suburb", "") or addr.get("quarter", "") or addr.get("neighbourhood", "")
        if suburb:
            parts.append(suburb)

        # Quận
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

        address = ", ".join(parts) if parts else display_name

        logger.info("[GEO] Resolved: (%.4f, %.4f) → %s", lat, lng, address[:80])

        # Cache lại
        cache_key = f"{lat},{lng}"
        _cache[cache_key] = (address, time.time())

        return GeoResult(
            address=address,
            district=district,
            city=city,
            country=addr.get("country", ""),
            lat=lat,
            lng=lng,
            raw=addr,
        )

    except urllib.error.URLError as e:
        logger.warning("[GEO] Network error: %s", str(e)[:100])
    except Exception as e:
        logger.warning("[GEO] Error: %s", str(e)[:100])

    # Fallback: trả tọa độ thô
    fallback = f"Tọa độ: {lat:.5f}, {lng:.5f}"
    return GeoResult(address=fallback, lat=lat, lng=lng)


def format_location_context(lat: float, lng: float) -> str:
    """
    Tạo context string ngắn gọn để inject vào System Prompt LLM.
    
    Ví dụ: "Người dùng đang ở: 62 KV4 NVC nối dài, Ninh Kiều, Cần Thơ"
    """
    geo = reverse_geocode(lat, lng)
    return f"Người dùng đang ở: {geo.address}"


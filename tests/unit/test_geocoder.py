"""Test Geocoder — Reverse geocode tọa độ Cần Thơ."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core.location.geocoder import reverse_geocode, format_location_context

# Tọa độ khu vực Ninh Kiều, Cần Thơ (gần 62 KV4 NVC nối dài)
lat, lng = 10.0296, 105.7684

print("=" * 60)
print("TEST REVERSE GEOCODE — 2 tầng (Google → Nominatim)")
print("=" * 60)

result = reverse_geocode(lat, lng)
print(f"Source  : {result.source}")
print(f"Address : {result.address}")
print(f"District: {result.district}")
print(f"City    : {result.city}")
print(f"Country : {result.country}")
print(f"Raw     : {result.raw}")

print()
print("FORMAT LOCATION CONTEXT:")
ctx = format_location_context(lat, lng)
print(ctx)

print()
if result.source == "google":
    print("✅ Dùng Google Geocoding API — chính xác nhất!")
elif result.source == "nominatim":
    print("⚠️ Dùng Nominatim (OSM) — không có Google API key, kém chi tiết hơn")
    print("💡 Tip: Thêm GOOGLE_MAPS_API_KEY vào .env để chính xác cấp số nhà!")
else:
    print(f"⚠️ Source: {result.source}")

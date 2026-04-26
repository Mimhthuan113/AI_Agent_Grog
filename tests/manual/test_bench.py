"""Benchmark v3 — dùng persistent httpx client"""
import time
import httpx

client = httpx.Client(base_url='http://localhost:8000', timeout=10)

r = client.post('/auth/login', json={
    'username': 'admin',
    'password': 'changeme_strong_password_here'
})
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Warmup
client.post('/chat', json={'message': 'test'}, headers=headers)

tests = [
    ("Xin chào", "greeting"),
    ("Mấy giờ rồi", "time"),
    ("Tên bạn là gì", "self_intro"),
    ("Bật đèn phòng ngủ", "smart_home"),
    ("Cảm ơn bạn", "thanks"),
    ("Tạm biệt", "goodbye"),
    ("Bạn dễ thương quá", "compliment"),
    ("Tắt quạt phòng khách", "smart_home"),
    ("Kể chuyện cười đi", "general_chat (LLM)"),
]

print("=" * 60)
print("BENCHMARK v3 — Persistent Client (mục tiêu < 2s)")
print("=" * 60)

for msg, category in tests:
    start = time.time()
    r = client.post('/chat', json={'message': msg}, headers=headers)
    elapsed = time.time() - start
    d = r.json()
    status = "✅" if elapsed < 1 else "⚠️" if elapsed < 2 else "❌"
    print(f"{status} [{elapsed:.3f}s] {category:20s} | {msg:25s} → {d['response'][:35]}")

print("=" * 60)
client.close()

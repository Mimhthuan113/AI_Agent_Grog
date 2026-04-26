"""Test Edge TTS — giọng HoaiMy nữ Việt Nam"""
import httpx

# Login
r = httpx.post('http://localhost:8000/auth/login', json={
    'username': 'admin',
    'password': 'changeme_strong_password_here'
})
token = r.json()['access_token']

# Test TTS
r2 = httpx.post(
    'http://localhost:8000/voice/tts',
    json={'text': 'Xin chào! Tôi là Aisha, trợ lý nhà thông minh của bạn. Rất vui được gặp bạn!'},
    headers={'Authorization': f'Bearer {token}'},
    timeout=30,
)

print(f"Status: {r2.status_code}")
print(f"Content-Type: {r2.headers.get('content-type')}")
print(f"Audio size: {len(r2.content)} bytes")

if r2.status_code == 200:
    with open('test_aisha_voice.mp3', 'wb') as f:
        f.write(r2.content)
    print("Saved to test_aisha_voice.mp3 — play it to hear HoaiMy female voice!")
else:
    print(f"Error: {r2.text[:200]}")

import httpx

r = httpx.post('http://localhost:8000/auth/login', json={
    'username': 'admin',
    'password': 'changeme_strong_password_here'
})
t = r.json()['access_token']

# Test 1: Smart home (có dấu)
r2 = httpx.post('http://localhost:8000/chat',
    json={'message': 'Bật đèn phòng ngủ'},
    headers={'Authorization': f'Bearer {t}'},
    timeout=30)
d = r2.json()
print(f"[1] Response: {d['response']}")
print(f"    Category: {d['category']}")
print(f"    Success: {d['success']}")

# Test 2: Greeting
r3 = httpx.post('http://localhost:8000/chat',
    json={'message': 'Xin chào'},
    headers={'Authorization': f'Bearer {t}'})
d3 = r3.json()
print(f"\n[2] Response: {d3['response']}")
print(f"    Category: {d3['category']}")

# Test 3: Time
r4 = httpx.post('http://localhost:8000/chat',
    json={'message': 'Mấy giờ rồi'},
    headers={'Authorization': f'Bearer {t}'})
d4 = r4.json()
print(f"\n[3] Response: {d4['response']}")
print(f"    Category: {d4['category']}")

# Test 4: General chat
r5 = httpx.post('http://localhost:8000/chat',
    json={'message': 'Kể cho tôi nghe chuyện cười'},
    headers={'Authorization': f'Bearer {t}'},
    timeout=30)
d5 = r5.json()
print(f"\n[4] Response: {d5['response']}")
print(f"    Category: {d5['category']}")

# Test 5: Self intro
r6 = httpx.post('http://localhost:8000/chat',
    json={'message': 'Tên bạn là gì'},
    headers={'Authorization': f'Bearer {t}'})
d6 = r6.json()
print(f"\n[5] Response: {d6['response']}")
print(f"    Category: {d6['category']}")

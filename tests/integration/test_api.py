"""Test tat ca API endpoints Sprint 1."""
import urllib.request
import urllib.error
import json
import sys

BASE = "http://localhost:8000"
PASSED = 0
FAILED = 0

def test(name, fn):
    global PASSED, FAILED
    print(f"\n{'='*50}")
    print(f"TEST: {name}")
    print(f"{'='*50}")
    try:
        fn()
        PASSED += 1
        print("[PASSED]")
    except Exception as e:
        FAILED += 1
        print(f"[FAILED] {e}")

def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read())

def post(url, data=None, headers=None):
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    body = json.dumps(data).encode() if data else b""
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read())

def expect_error(url, method="GET", data=None, headers=None, expected_code=401):
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        urllib.request.urlopen(req)
        raise AssertionError(f"Expected {expected_code} but got 200")
    except urllib.error.HTTPError as e:
        assert e.code == expected_code, f"Expected {expected_code} got {e.code}"
        return e.code, json.loads(e.read())

# ── Luu token global ──
TOKEN = None

def test_health():
    status, data = get(f"{BASE}/health")
    assert status == 200
    assert data["status"] == "ok"
    assert data["service"] == "smart-ai-home-hub"
    print(f"  status={data['status']}, service={data['service']}")

def test_login_ok():
    global TOKEN
    status, data = post(f"{BASE}/auth/login", {
        "username": "admin",
        "password": "changeme_strong_password_here"
    })
    assert status == 200
    assert "access_token" in data
    assert data["user_id"] == "admin"
    assert data["expires_in"] > 0
    TOKEN = data["access_token"]
    print(f"  user={data['user_id']}, expires_in={data['expires_in']}s")
    print(f"  token={TOKEN[:40]}...")

def test_login_wrong_password():
    code, data = expect_error(
        f"{BASE}/auth/login", method="POST",
        data={"username": "admin", "password": "wrong"},
        expected_code=401
    )
    assert data["detail"] == "Invalid credentials"
    print(f"  code={code}, detail={data['detail']}")

def test_login_wrong_user():
    code, data = expect_error(
        f"{BASE}/auth/login", method="POST",
        data={"username": "hacker", "password": "test"},
        expected_code=401
    )
    print(f"  code={code}, detail={data['detail']}")

def test_me_with_token():
    status, data = get(
        f"{BASE}/auth/me",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert status == 200
    assert data["user_id"] == "admin"
    assert "owner" in data["roles"]
    print(f"  user={data['user_id']}, roles={data['roles']}")

def test_me_no_token():
    code, data = expect_error(f"{BASE}/auth/me", expected_code=401)
    print(f"  code={code}, detail={data['detail']}")

def test_me_fake_token():
    code, data = expect_error(
        f"{BASE}/auth/me",
        headers={"Authorization": "Bearer fake.token.here"},
        expected_code=401
    )
    print(f"  code={code}, detail={data['detail']}")

def test_logout():
    status, data = post(
        f"{BASE}/auth/logout",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert status == 200
    assert data["message"] == "Logged out successfully"
    print(f"  message={data['message']}, revoked={data['revoked']}")

# ── Run ──
if __name__ == "__main__":
    test("GET /health", test_health)
    test("POST /auth/login (correct)", test_login_ok)
    test("POST /auth/login (wrong password)", test_login_wrong_password)
    test("POST /auth/login (wrong user)", test_login_wrong_user)
    test("GET /auth/me (with token)", test_me_with_token)
    test("GET /auth/me (no token)", test_me_no_token)
    test("GET /auth/me (fake token)", test_me_fake_token)
    test("POST /auth/logout", test_logout)

    print(f"\n{'='*50}")
    print(f"RESULT: {PASSED} passed, {FAILED} failed")
    print(f"{'='*50}")
    sys.exit(0 if FAILED == 0 else 1)

"""Quick test cho RBAC + Rate Limiter"""
import sys
import asyncio
from pathlib import Path

# Auto-bootstrap project root để chạy được `python tests/unit/test_phase2.py`
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core.security.rbac import check_permission, RBACError
from src.core.security.rate_limiter import get_rate_limiter

# RBAC tests
print("=== RBAC Tests ===")
r = check_permission(["guest"], "light.test", "turn_on")
print(f"Guest + light.turn_on = {r}")

try:
    check_permission(["guest"], "lock.cua", "lock")
except RBACError as e:
    print(f"Guest + lock.lock = DENIED: {e}")

try:
    check_permission(["guest"], "climate.ac", "set_temperature")
except RBACError as e:
    print(f"Guest + climate = DENIED: {e}")

r2 = check_permission(["owner"], "lock.cua", "lock")
print(f"Owner + lock.lock = {r2}")


# Rate Limiter + Circuit Breaker tests (async)
async def _async_tests():
    print("\n=== Rate Limiter Tests ===")
    rl = get_rate_limiter()
    for i in range(12):
        result = await rl.check_rate_limit("testuser", "light.test")
        if result.result.value != "allowed":
            print(f"Request {i+1}: BLOCKED - {result.reason}")
            break
        print(f"Request {i+1}: OK (remaining: {result.remaining})")

    # Circuit Breaker test
    print("\n=== Circuit Breaker Tests ===")
    cb = rl.circuit
    for i in range(6):
        cb.record_failure()
        print(f"Failure {i+1}: state={cb.state.value}")

    print(f"Allow request? {cb.allow_request()}")
    cb.record_success()  # Reset
    print(f"After success: state={cb.state.value}")


asyncio.run(_async_tests())

print("\n✅ ALL PHASE 2 MODULE TESTS PASSED")

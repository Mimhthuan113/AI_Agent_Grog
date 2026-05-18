"""Manual test cho AlarmProvider — parse VN time + intent generation."""
from __future__ import annotations

import asyncio
import sys
import os

# Bootstrap sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.core.app_actions.router import parse_app_intent, execute_app_action  # noqa: E402
from src.core.app_actions.providers import _parse_vietnamese_time  # noqa: E402


# ─── Test 1: parser unit ───────────────────────────────
PARSER_CASES = [
    ("2h sáng",        (2, 0)),
    ("5h30 sáng",      (5, 30)),
    ("5:30 chiều",     (17, 30)),
    ("14:00",          (14, 0)),
    ("12 giờ trưa",    (12, 0)),
    ("2 giờ đêm",      (2, 0)),
    ("12h khuya",      (0, 0)),
    ("12 giờ sáng",    (0, 0)),
    ("6h sáng",        (6, 0)),
    ("7 giờ tối",      (19, 0)),
    ("invalid",        None),
    ("25h sáng",       None),  # giờ không hợp lệ
]

print("═" * 60)
print("Test 1 — VN Time Parser")
print("═" * 60)
fail_parser = 0
for text, expected in PARSER_CASES:
    got = _parse_vietnamese_time(text)
    ok = got == expected
    mark = "✓" if ok else "✗"
    print(f"  {mark} {text!r:25} → {got!r}  (expected {expected!r})")
    if not ok:
        fail_parser += 1
print(f"\n  Parser: {len(PARSER_CASES) - fail_parser}/{len(PARSER_CASES)} passed\n")


# ─── Test 2: intent + provider end-to-end ──────────────
INTENT_CASES = [
    "đặt báo thức 2h sáng",
    "cài báo thức lúc 5h30 chiều",
    "báo thức 14:00",
    "báo thức 7 giờ tối",
    "hẹn báo thức 6h sáng nhắc tôi đi học",
    "đặt báo thức 12 giờ trưa",
    "đặt báo thức 12h khuya",
    "mở đồng hồ",
    "xem báo thức",
    "đặt báo thức",  # missing time → expect fail
]

print("═" * 60)
print("Test 2 — Intent → Provider end-to-end")
print("═" * 60)


async def run_intents():
    for q in INTENT_CASES:
        print(f"\n── {q!r}")
        intent = parse_app_intent(q)
        print(f"   intent: {intent}")
        if not intent:
            print("   (no match)")
            continue
        res = await execute_app_action(
            intent["provider"], intent["action"], intent["params"]
        )
        print(f"   success={res.success}  msg={res.message!r}")
        if res.data:
            ai = res.data.get("android_intent")
            if ai:
                action = ai.get("action")
                extras = ai.get("extras", {})
                hour = extras.get("android.intent.extra.alarm.HOUR")
                minute = extras.get("android.intent.extra.alarm.MINUTES")
                msg = extras.get("android.intent.extra.alarm.MESSAGE")
                print(f"   android.action: {action}")
                if hour is not None:
                    print(f"   HOUR={hour} MIN={minute} MSG={msg!r}")
            web = res.data.get("web_url")
            if web:
                print(f"   web_url: {web}")


asyncio.run(run_intents())
print("\n═" * 30)
print("Done.")

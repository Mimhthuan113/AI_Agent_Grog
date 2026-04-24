"""
SSE Monitor — phát sự kiện pipeline realtime cho dashboard giám sát.

Mỗi khi gateway xử lý 1 request, event được broadcast qua SSE.
Monitor app (chạy tách biệt) kết nối vào đây để theo dõi realtime.
"""
import asyncio
import json
import time
import logging
from collections import deque
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitor", tags=["monitor"])

# ── Event Store ────────────────────────────────────────────
# Lưu 100 events gần nhất + broadcast cho connected clients
_event_queue: deque[dict] = deque(maxlen=200)
_subscribers: list[asyncio.Queue] = []


def broadcast_event(event: dict):
    """Gọi từ gateway/agent để broadcast 1 event ra tất cả monitor clients."""
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    event["ts_ms"] = int(time.time() * 1000)
    _event_queue.append(event)
    for q in _subscribers:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass  # Client quá chậm — bỏ qua


def emit_pipeline_event(
    user_id: str,
    message: str,
    category: str,
    steps: list[dict] | None,
    result: str,
    success: bool,
    request_id: str = "",
):
    """Helper: emit 1 pipeline event hoàn chỉnh."""
    broadcast_event({
        "type": "pipeline",
        "user_id": user_id,
        "message": message,
        "category": category,
        "steps": steps or [],
        "result": result,
        "success": success,
        "request_id": request_id,
    })


# ── SSE Endpoint ──────────────────────────────────────────

@router.get("/events")
async def monitor_stream(request: Request):
    """SSE stream — monitor dashboard kết nối vào đây."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.append(queue)

    # Gửi history trước
    for evt in list(_event_queue)[-20:]:
        await queue.put(evt)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield {
                        "event": event.get("type", "pipeline"),
                        "data": json.dumps(event, ensure_ascii=False),
                    }
                except asyncio.TimeoutError:
                    # Heartbeat để giữ kết nối
                    yield {
                        "event": "ping",
                        "data": json.dumps({"ts": int(time.time() * 1000)}),
                    }
        finally:
            _subscribers.remove(queue)

    return EventSourceResponse(event_generator())


@router.get("/history")
async def monitor_history():
    """Lấy 50 events gần nhất."""
    return list(_event_queue)[-50:]

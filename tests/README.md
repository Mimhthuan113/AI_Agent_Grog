# 🧪 Aisha Test Suite

Cấu trúc tests đã được dọn dẹp ngày 2026-04-26 — gom toàn bộ test scripts
ở thư mục gốc về `tests/` theo phân loại rõ ràng.

## Cấu trúc thư mục

```
tests/
├── conftest.py              # Auto-inject project root vào sys.path
├── README.md                # File này
├── unit/                    # Test thuần module — KHÔNG cần server chạy
│   ├── test_security.py     # Schema validate + Sanitizer
│   ├── test_phase2.py       # RBAC + Rate Limiter direct import
│   ├── test_geocoder.py     # Reverse geocoding (cần network)
│   └── test_groq_keys.py    # Groq API key validation
├── integration/             # Test end-to-end qua HTTP — CẦN server chạy
│   ├── test_integration.py  # Full pipeline 7 phases
│   ├── test_api.py          # Auth + Chat + Devices + Audit
│   ├── test_chat.py         # Chat endpoint cơ bản
│   ├── test_siri.py         # Siri Brain category routing
│   └── test_injection.py    # 20 prompt injection vectors
├── manual/                  # Chạy thủ công — kiểm tra tính năng đặc thù
│   ├── test_bench.py        # Benchmark response time
│   ├── test_voices.py       # Edge TTS list voices
│   └── test_tts.py          # Edge TTS sample MP3
└── security/                # (legacy folder — sẽ deprecate)
```

## Cách chạy

### 1. Unit tests (nhanh, không cần server)

```powershell
# Cài pytest
pip install pytest

# Chạy toàn bộ unit tests
pytest tests/unit/ -v

# Chạy 1 file cụ thể
pytest tests/unit/test_security.py -v
```

### 2. Integration tests (cần server `uvicorn` chạy)

```powershell
# Terminal 1 — start server
uvicorn src.api.app:app --reload --port 8000

# Terminal 2 — chạy test
python tests/integration/test_integration.py
python tests/integration/test_injection.py
```

### 3. Manual tests

```powershell
# Cần GROQ_API_KEY hoặc microphone hoạt động
python tests/manual/test_bench.py
python tests/manual/test_voices.py
```

## Lưu ý

- `conftest.py` tự động inject project root vào `sys.path` → mọi `from src.xxx import yyy` đều chạy.
- Không cần sửa `sys.path.insert(0, ".")` thủ công nữa.
- Các file MP3 artifact (`test_aisha_voice.mp3`, `test_gtts.mp3`) đã bị xoá khỏi root — TTS sẽ tự sinh khi chạy test.

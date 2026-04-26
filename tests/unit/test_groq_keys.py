"""
Manual validator các Groq API keys.

KHÔNG hardcode key vào source — đọc từ env var hoặc file local.

Cách dùng:
    # Cách 1: Truyền nhiều key qua env (ngăn cách bằng dấu phẩy)
    set GROQ_API_KEYS=gsk_xxx1,gsk_xxx2,gsk_xxx3
    python tests/unit/test_groq_keys.py

    # Cách 2: Tạo file `tests/unit/.groq_keys.local` (đã .gitignore),
    # mỗi key 1 dòng, các dòng bắt đầu bằng # bỏ qua.
"""
import os
import sys
import urllib.request
import urllib.error
import json
from pathlib import Path


def _load_keys() -> list[str]:
    """Load keys theo thứ tự ưu tiên: env GROQ_API_KEYS → file local → empty."""
    env = os.getenv("GROQ_API_KEYS", "").strip()
    if env:
        return [k.strip() for k in env.split(",") if k.strip()]

    local_file = Path(__file__).with_name(".groq_keys.local")
    if local_file.exists():
        out = []
        for line in local_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(line)
        return out

    return []


keys = _load_keys()

def test_groq_key(api_key):
    # Dùng endpoint /models của OpenAI compatibility layer của Groq
    url = "https://api.groq.com/openai/v1/models"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                models = len(data.get('data', []))
                print(f"✅ Key {api_key[:8]}...{api_key[-4:]} [HỢP LỆ] - Có quyền truy cập {models} models!")
    except urllib.error.HTTPError as e:
        print(f"❌ Key {api_key[:8]}...{api_key[-4:]} [LỖI] - HTTP {e.code}: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"❌ Key {api_key[:8]}...{api_key[-4:]} [LỖI KẾT NỐI] - {e}")

if __name__ == "__main__":
    if not keys:
        print(
            "⚠️  Không tìm thấy Groq API key nào để kiểm tra.\n"
            "   Đặt env var GROQ_API_KEYS=gsk_xxx,gsk_yyy\n"
            "   Hoặc tạo file tests/unit/.groq_keys.local (mỗi dòng 1 key)."
        )
        sys.exit(0)

    print(f"🚀 Bắt đầu kiểm tra {len(keys)} Groq API Keys...\n")
    for key in keys:
        if key.strip():
            test_groq_key(key.strip())
    print("\n✅ Hoàn thành!")

# 🗺️ Workflow — Luồng Xử Lý Aisha

> Sơ đồ theo dõi tiến trình từng request đi qua hệ thống.

---

## 1. Tổng Quan — User Flow

```mermaid
flowchart TD
    A["👤 User mở app"] --> B{"Có token<br/>trong localStorage?"}
    B -->|Không| C["📱 Login Page"]
    B -->|Có| D{"Token hợp lệ?<br/>GET /auth/me"}

    D -->|Hết hạn / sai| C
    D -->|OK| E{"Role?"}

    C --> F["Nhập username + password"]
    F --> G["POST /auth/login"]
    G -->|401| H["❌ Sai thông tin"]
    H --> F
    G -->|200 + JWT| I["Lưu token + roles<br/>vào localStorage"]
    I --> E

    E -->|owner| J["🏠 Full Access<br/>Chat + Devices + History"]
    E -->|guest| K["🔒 Limited Access<br/>Chat + Devices"]

    J --> L["💬 Chat Page"]
    K --> L
```

---

## 2. Security Gateway Pipeline — 6 Lớp Bảo Mật

```mermaid
flowchart TD
    START["📨 POST /chat<br/>user gửi câu tiếng Việt"] --> AUTH["🔐 JWT Middleware"]
    AUTH -->|401| KICK["⛔ Kick ra Login"]
    AUTH -->|OK| BRAIN["🧠 Siri Brain<br/>phân loại intent"]

    BRAIN -->|greeting / time| INSTANT["⚡ Instant Response<br/>3ms"]
    BRAIN -->|general_chat| LLM["🤖 Groq LLM<br/>timeout 3s"]
    BRAIN -->|dangerous| BLOCK["🛡️ Chặn"]
    BRAIN -->|smart_home| PARSE["📝 Intent Parser"]

    PARSE --> GW0["⏱ Step 0: Rate Limiter"]
    GW0 -->|BLOCKED| DENY["❌ DENIED + Audit"]
    GW0 -->|OK| GW1["🧹 Step 1: Sanitizer"]

    GW1 -->|INJECTION| DENY
    GW1 -->|CLEAN| GW1B["👥 Step 1b: RBAC"]

    GW1B -->|DENIED| DENY
    GW1B -->|OK| GW2["📜 Step 2: Rule Engine"]

    GW2 -->|DENIED| DENY
    GW2 -->|WARNING| CONFIRM["✋ Cần xác nhận"]
    GW2 -->|SAFE| GW2C["⚡ Step 2c: Circuit Breaker"]

    GW2C -->|OPEN| DENY
    GW2C -->|CLOSED| GW3["🏠 Step 3: Execute HA"]

    GW3 --> GW4["📋 Step 4: Audit Log"]
    GW4 --> RESP["✅ Response → User"]
```

---

## 3. Confirmation Flow — Lệnh Nguy Hiểm

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as API Server
    participant GW as Gateway
    participant Store as Pending Store

    User->>FE: "Tắt điều hoà"
    FE->>API: POST /chat
    API->>GW: process_command
    GW-->>API: requires_confirmation = true
    API->>Store: Lưu pending (TTL 60s)
    API-->>FE: response + request_id

    FE->>FE: Hiện Confirm Modal

    alt Xác nhận
        User->>FE: Nhấn Xác nhận
        FE->>API: POST /chat/confirm
        API->>GW: Thực thi
        API-->>FE: Thành công
    else Huỷ
        User->>FE: Nhấn Huỷ
        FE->>API: POST /chat/confirm (confirmed=false)
        API-->>FE: Đã huỷ
    end
```

---

## 4. RBAC — Bảng Phân Quyền

| Entity            | Action                    |      👑 Owner       |  👤 Guest   |
| ----------------- | ------------------------- | :-----------------: | :---------: |
| `light.*`         | turn_on/off, brightness   |         ✅          |     ✅      |
| `light.*`         | set_color                 |         ✅          |     ❌      |
| `sensor.*`        | get_state                 |         ✅          |     ✅      |
| `climate.*`       | set_temperature, turn_off |    ✅ ⚠️ confirm    |     ❌      |
| `lock.*`          | lock                      |         ✅          |     ❌      |
| `lock.*`          | unlock                    | ❌ (chặn tuyệt đối) |     ❌      |
| `switch.kitchen*` | turn_off                  |    ✅ ⚠️ confirm    |     ❌      |
| `switch.kitchen*` | turn_on                   | ❌ (chặn tuyệt đối) |     ❌      |
| Audit log         | xem                       |         ✅          | ❌ (ẩn tab) |

---

## 5. Token Lifecycle

```mermaid
stateDiagram-v2
    [*] --> NoToken: App mở
    NoToken --> Login: Hiện Login Page
    Login --> HasToken: POST /auth/login
    HasToken --> Active: GET /auth/me OK
    Active --> Active: Gửi JWT mỗi request
    Active --> Expired: Hết hạn 15 phút
    Expired --> NoToken: 401 → Auto clear
    Active --> Logout: User logout
    Logout --> NoToken: Redis blacklist + clear
```

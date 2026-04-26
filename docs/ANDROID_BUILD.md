# Đóng gói Aisha thành APK Android (Capacitor)

Hướng dẫn từng bước biến frontend React + Vite hiện tại thành 1 APK chạy trên
điện thoại Android, dùng [Capacitor 6](https://capacitorjs.com/).

> 📌 **Lưu ý:** Repo đã cấu hình sẵn:
> - `@capacitor/core` + `@capacitor/android` + `@capacitor/cli` trong `frontend/package.json`
> - `@capacitor-community/speech-recognition` (giúp wake-word + voice input chạy native trong APK)
> - `frontend/capacitor.config.json`
> - Backend `CORS_ORIGINS` mặc định đã bao gồm `capacitor://localhost`, `https://localhost`
> - Trang **Account → Cấu hình kết nối Backend** cho phép nhập URL backend ngay trong app
> - Script `npm run setup:env` tự dò IP LAN ghi vào `.env.production`
>
> Bạn chỉ cần cài JDK + Android SDK rồi chạy các bước bên dưới.

---

## 1. Yêu cầu môi trường (Windows)

| Công cụ            | Phiên bản tối thiểu | Ghi chú                                                |
| ------------------ | ------------------- | ------------------------------------------------------ |
| **Node.js**        | 20+                 | đã cài sẵn cho project                                  |
| **JDK**            | 21 (Temurin / Oracle) | bắt buộc cho Capacitor 6                              |
| **Android Studio** | Hedgehog 2023.1.1+  | dùng SDK Manager để cài Platform 34 + Build Tools 34   |
| **Android SDK**    | API 34+             | đặt biến môi trường `ANDROID_HOME`                     |
| **Gradle**         | wrapper             | Capacitor sẽ tự dùng `gradlew.bat` đi kèm              |

Biến môi trường nên có:

```powershell
# PowerShell (user-level)
[Environment]::SetEnvironmentVariable("JAVA_HOME", "C:\Program Files\Eclipse Adoptium\jdk-21", "User")
[Environment]::SetEnvironmentVariable("ANDROID_HOME", "$env:LOCALAPPDATA\Android\Sdk", "User")
[Environment]::SetEnvironmentVariable(
  "Path",
  "$env:Path;$env:JAVA_HOME\bin;$env:ANDROID_HOME\platform-tools;$env:ANDROID_HOME\tools\bin",
  "User"
)
```

> Mở lại terminal sau khi set biến môi trường.

---

## 2. Cài dependency frontend

```powershell
cd frontend
npm install
```

Các package Capacitor sẽ tự được cài cùng (đã ghi trong `package.json`).

---

## 3. Build web bundle

```powershell
npm run build
```

Vite output ra `frontend/dist/` — Capacitor sẽ copy bundle này vào project Android.

---

## 4. Thêm platform Android (chỉ chạy lần đầu)

```powershell
npx cap add android
```

Lệnh này tạo thư mục `frontend/android/` chứa project Gradle hoàn chỉnh.
**Commit cả thư mục này vào git** (Capacitor recommend) để team build lại được.

> Nếu lệnh báo *"Capacitor could not find a capacitor.config.*"*, đảm bảo bạn
> đang đứng trong `frontend/`.

---

## 5. Cấu hình URL backend (quan trọng)

App Capacitor chạy trên điện thoại sẽ **không** gọi được `http://localhost:8000`
(localhost = chính điện thoại, không phải PC). Cần trỏ tới IP LAN của máy chạy backend.

### 5.1. Cách tự động (khuyến nghị)

```powershell
cd frontend
npm run setup:env          # auto chọn IP LAN (192.168.* > 10.* > 172.*)
# hoặc:
npm run setup:env:i        # tương tác — chọn IP nếu có nhiều
```

Script `scripts/setup-env.mjs` sẽ:
- Quét `os.networkInterfaces()`, lọc IPv4 nội bộ.
- Bỏ qua interface ảo (vEthernet, WSL, Docker, VMWare, Hyper-V).
- Ưu tiên `192.168.*` → `10.*` → `172.16-31.*`.
- Ghi `frontend/.env.production` với `VITE_API_URL=http://<IP>:8000`.

> 💡 **Tip:** `npm run android:apk` đã tự gọi `setup:env` trước khi build.
> Bạn không cần chạy thủ công nếu chỉ build APK.

### 5.2. Override URL ngay trong app (không cần build lại)

Sau khi cài APK lần đầu:
1. Mở app → tab **Tài khoản** → mục **🔌 Cấu hình kết nối Backend**.
2. Nhập IP LAN của máy chạy backend, ví dụ `http://192.168.1.10:8000`.
3. Bấm **🔍 Test kết nối** để kiểm tra → 💾 **Lưu**.

URL được lưu trong `localStorage` và sẽ ưu tiên hơn build-time `VITE_API_URL`.
Bấm **↺ Reset** để quay về URL mặc định.

### 5.3. Cấu hình CORS phía backend

Backend mặc định đã cho phép các origin Capacitor — kiểm tra `.env`:

```env
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,capacitor://localhost,https://localhost,ionic://localhost
```

Nếu deploy production (HTTPS), thêm domain thật:
```env
CORS_ORIGINS=...,https://aisha.vn,https://app.aisha.vn
```

> ⚠️ Backend phải bind `0.0.0.0` (không phải `127.0.0.1`) thì điện thoại mới
> truy cập được qua LAN. Trong `.env`: `APP_HOST=0.0.0.0`.

---

## 6. Cấp quyền Android (RECORD_AUDIO, INTERNET, GPS)

Mở `frontend/android/app/src/main/AndroidManifest.xml`, thêm vào trong thẻ
`<manifest>` (trước thẻ `<application>`):

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />

<!-- Cho phép Speech Recognition trên Android 11+ (package visibility) -->
<queries>
    <intent>
        <action android:name="android.speech.RecognitionService" />
    </intent>
</queries>
```

### Speech Recognition đã hoạt động native

Repo đã cài sẵn `@capacitor-community/speech-recognition@^6`. Cả wake-word
("Hey Aisha") và voice command sẽ tự dùng `android.speech.SpeechRecognizer`
khi chạy trong APK, fallback Web Speech API khi mở browser:

- **`useWakeWord` hook** → detect `Capacitor.isNativePlatform()`, chọn backend
  phù hợp, restart liên tục (Android giới hạn ~10s/session).
- **`VoiceOrb` component** → tương tự, hiển thị transcript real-time qua
  event `partialResults` của plugin.

Frontend tự gọi `SpeechRecognition.requestPermissions()` lần đầu — user sẽ thấy
dialog cấp quyền micro.

---

## 7. Build APK debug (nhanh, không ký)

### Cách 1 — qua npm script

```powershell
npm run android:apk
```

Script trên sẽ:
1. `vite build`
2. `cap sync android`
3. `cd android && gradlew.bat assembleDebug`

APK output:
`frontend/android/app/build/outputs/apk/debug/app-debug.apk`

Copy file APK sang điện thoại, bật *"Cài đặt từ nguồn không xác định"* → cài.

### Cách 2 — qua Android Studio (khuyến nghị lần đầu)

```powershell
npx cap open android
```

Trong Android Studio:
- Chờ Gradle sync xong (~3-5 phút lần đầu).
- Menu **Build → Build Bundle(s) / APK(s) → Build APK(s)**.
- Khi xong, click *"locate"* để mở thư mục chứa APK.

---

## 8. Build APK release (đã ký)

1. Tạo keystore (1 lần):

   ```powershell
   keytool -genkey -v -keystore aisha-release.keystore -alias aisha `
       -keyalg RSA -keysize 2048 -validity 10000
   ```

2. Tạo `frontend/android/key.properties`:

   ```properties
   storeFile=../aisha-release.keystore
   storePassword=<mật khẩu store>
   keyAlias=aisha
   keyPassword=<mật khẩu key>
   ```

3. Sửa `frontend/android/app/build.gradle` thêm khối `signingConfigs.release`
   trỏ tới `key.properties` (Capacitor docs có template chi tiết).

4. Build:

   ```powershell
   cd frontend\android
   .\gradlew.bat assembleRelease
   ```

   Output: `frontend/android/app/build/outputs/apk/release/app-release.apk`

---

## 9. Live reload khi dev (tuỳ chọn)

Sửa `frontend/capacitor.config.json` thêm khối `server.url`:

```json
{
  "server": {
    "androidScheme": "https",
    "cleartext": true,
    "url": "http://192.168.1.10:5173"
  }
}
```

Rồi:

```powershell
# Terminal 1: vite dev server bind 0.0.0.0
cd frontend
npm run dev -- --host 0.0.0.0

# Terminal 2: chạy app trên thiết bị Android
npx cap run android
```

App trên điện thoại sẽ load trực tiếp từ Vite dev server → hot reload.

> **Nhớ xoá `server.url`** trước khi build APK release.

---

## 10. Troubleshooting

| Lỗi                                                | Cách xử lý                                                                                       |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `SDK location not found`                           | Tạo `frontend/android/local.properties` với `sdk.dir=C\:\\Users\\<bạn>\\AppData\\Local\\Android\\Sdk` |
| `Unsupported Java …`                               | Dùng đúng JDK 21. Kiểm tra: `java -version`                                                     |
| `CleartextTrafficException` khi gọi API HTTP      | Backend chạy HTTPS, hoặc giữ `cleartext: true` + `usesCleartextTraffic="true"` trong manifest    |
| `App crash mở mic`                                 | Thiếu `RECORD_AUDIO` permission trong `AndroidManifest.xml` (xem mục 6)                          |
| `gradlew.bat: command not found`                   | Bạn đang ở sai thư mục — phải đứng trong `frontend/android/`                                     |
| Web app trắng xoá khi mở APK                       | Mở Chrome → `chrome://inspect/#devices` để debug WebView. Thường do `VITE_API_URL` sai.          |

---

## 11. Checklist trước khi phát hành

- [ ] Đặt `VITE_API_URL` trong `.env.production` trỏ tới backend public (HTTPS).
- [ ] Backend bật HTTPS (Let's Encrypt / Cloudflare).
- [ ] Đảm bảo `CORS_ORIGINS` cho phép `capacitor://localhost`, `https://localhost`, và domain thật.
  (Mặc định trong `src/config.py` đã có sẵn 3 origin Capacitor.)
- [ ] Đổi `appId` `vn.aisha.app` thành domain thật của bạn (vd `vn.example.aisha`).
- [ ] Thay icon launcher: `frontend/android/app/src/main/res/mipmap-*/ic_launcher.png`.
- [ ] Build `assembleRelease` đã ký bằng keystore.
- [ ] Test wake-word "Hey Aisha" thật + voice command thật trên thiết bị (cần cấp quyền micro).
- [ ] Test trên ít nhất 2 hãng (Samsung, Xiaomi, Pixel) để chắc Android SpeechRecognizer chạy ổn.

---

> Tài liệu chính thức Capacitor: <https://capacitorjs.com/docs/android>

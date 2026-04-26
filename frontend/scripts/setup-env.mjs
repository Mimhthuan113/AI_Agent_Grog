#!/usr/bin/env node
/**
 * setup-env.mjs — Tự detect IP LAN của máy → ghi vào .env.production
 *
 * Khi build APK Capacitor, frontend chạy trong WebView Android không thể
 * gọi `localhost:8000` (vì localhost = chính điện thoại, không phải PC).
 *
 * Script này:
 * 1. Quét tất cả network interfaces, lọc IP IPv4 nội bộ (192.168.*, 10.*, 172.16-31.*).
 * 2. Hỏi user chọn IP nếu có nhiều (hoặc lấy IP đầu tiên nếu chỉ 1).
 * 3. Ghi `frontend/.env.production` với VITE_API_URL = http://<IP>:8000.
 *
 * Cách dùng:
 *   cd frontend
 *   npm run setup:env           # auto chọn IP đầu tiên
 *   npm run setup:env -- --interactive   # hỏi nếu có nhiều IP
 *   npm run setup:env -- --port=9000     # đổi port (mặc định 8000)
 */

import { networkInterfaces } from 'node:os'
import { writeFile, readFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createInterface } from 'node:readline/promises'

const __dirname = dirname(fileURLToPath(import.meta.url))
const FRONTEND_ROOT = resolve(__dirname, '..')
const ENV_FILE = resolve(FRONTEND_ROOT, '.env.production')

const args = process.argv.slice(2)
const interactive = args.includes('--interactive') || args.includes('-i')
const portArg = args.find((a) => a.startsWith('--port='))
const port = portArg ? portArg.slice(7) : '8000'

/**
 * Trả về list IP IPv4 nội bộ, sort theo độ ưu tiên cho Wi-Fi/Ethernet thật:
 *   1. 192.168.*   (mạng gia đình phổ biến)
 *   2. 10.*        (mạng văn phòng / doanh nghiệp)
 *   3. 172.16-31.* (Docker/WSL → ít khả năng là Wi-Fi LAN)
 * Loại bỏ loopback, APIPA, virtual interfaces (vEthernet, WSL).
 */
function listLanIPs() {
  const found = []
  const ifaces = networkInterfaces()

  for (const [name, addrs] of Object.entries(ifaces)) {
    if (!addrs) continue
    // Bỏ qua interface ảo phổ biến của Docker/WSL/VMWare/Hyper-V
    const lower = name.toLowerCase()
    const isVirtual =
      lower.includes('vethernet') ||
      lower.includes('wsl') ||
      lower.includes('vmware') ||
      lower.includes('virtualbox') ||
      lower.includes('hyper-v') ||
      lower.includes('docker') ||
      lower.includes('loopback')
    for (const a of addrs) {
      if (a.family !== 'IPv4' && a.family !== 4) continue
      if (a.internal) continue
      const ip = a.address
      if (ip.startsWith('169.254.')) continue  // APIPA
      let priority
      if (ip.startsWith('192.168.')) priority = 1
      else if (ip.startsWith('10.')) priority = 2
      else if (/^172\.(1[6-9]|2\d|3[0-1])\./.test(ip)) priority = 3
      else continue  // không phải private → bỏ
      // Hạ priority cho virtual iface (vẫn giữ để user có thể chọn nếu interactive)
      if (isVirtual) priority += 10
      found.push({ ip, iface: name, priority })
    }
  }
  found.sort((a, b) => a.priority - b.priority)
  return found
}

async function pickIP(ips) {
  if (ips.length === 0) {
    console.error('❌ Không tìm thấy IP LAN nào. Bạn đã kết nối Wi-Fi/Ethernet chưa?')
    process.exit(1)
  }
  if (ips.length === 1 || !interactive) {
    return ips[0]
  }
  console.log('🔍 Tìm thấy nhiều IP LAN, chọn 1:')
  ips.forEach((x, i) => console.log(`   [${i + 1}] ${x.ip.padEnd(16)} (${x.iface})`))
  const rl = createInterface({ input: process.stdin, output: process.stdout })
  const ans = (await rl.question('→ Nhập số (mặc định 1): ')).trim()
  rl.close()
  const idx = ans ? parseInt(ans, 10) - 1 : 0
  if (Number.isNaN(idx) || idx < 0 || idx >= ips.length) {
    console.error('❌ Lựa chọn không hợp lệ.')
    process.exit(1)
  }
  return ips[idx]
}

/**
 * Đọc env hiện tại (nếu có) → preserve các biến khác (VITE_GOOGLE_CLIENT_ID, …).
 */
async function readExistingEnv() {
  if (!existsSync(ENV_FILE)) return new Map()
  try {
    const raw = await readFile(ENV_FILE, 'utf-8')
    const map = new Map()
    for (const line of raw.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith('#')) continue
      const eq = trimmed.indexOf('=')
      if (eq === -1) continue
      map.set(trimmed.slice(0, eq).trim(), trimmed.slice(eq + 1))
    }
    return map
  } catch {
    return new Map()
  }
}

async function main() {
  console.log('🌐 Aisha — setup-env.mjs')
  console.log(`📍 Thư mục: ${FRONTEND_ROOT}`)

  const ips = listLanIPs()
  const chosen = await pickIP(ips)
  const apiUrl = `http://${chosen.ip}:${port}`

  const existing = await readExistingEnv()
  existing.set('VITE_API_URL', apiUrl)
  if (!existing.has('VITE_GOOGLE_CLIENT_ID')) {
    existing.set('VITE_GOOGLE_CLIENT_ID', '')
  }

  // Build file content
  const header = [
    '# ============================================================',
    '# Aisha — .env.production (auto-generated bởi setup-env.mjs)',
    `# Tạo lúc: ${new Date().toISOString()}`,
    `# IP LAN: ${chosen.ip} (${chosen.iface})`,
    '# Chỉnh tay nếu cần. Chạy lại `npm run setup:env` để cập nhật IP.',
    '# ============================================================',
    '',
  ].join('\n')

  const body = Array.from(existing.entries())
    .map(([k, v]) => `${k}=${v}`)
    .join('\n')

  await writeFile(ENV_FILE, header + body + '\n', 'utf-8')

  console.log('')
  console.log(`✅ Đã ghi ${ENV_FILE}`)
  console.log(`   VITE_API_URL = ${apiUrl}`)
  console.log('')
  console.log('🚀 Tiếp theo:')
  console.log('   1. Đảm bảo backend đang chạy: python -m uvicorn src.api.app:create_app --factory --host 0.0.0.0')
  console.log('   2. Build APK:               npm run android:apk')
  console.log('   3. Mở trên điện thoại — App tự kết nối tới backend qua IP LAN ở trên.')
}

main().catch((e) => {
  console.error('💥 Lỗi:', e)
  process.exit(1)
})

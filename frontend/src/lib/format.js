/**
 * Helper format các string hiển thị.
 */

/**
 * Rút gọn tên hiển thị:
 * - Nếu là email → lấy phần trước @ và viết hoa chữ đầu
 * - Nếu là tên thường → giữ nguyên
 * - Nếu rỗng → 'User'
 *
 * @param {string|null|undefined} raw
 * @returns {string}
 */
export function formatDisplayName(raw) {
  if (!raw) return 'User'
  if (raw.includes('@')) {
    const name = raw.split('@')[0]
    return name.charAt(0).toUpperCase() + name.slice(1)
  }
  return raw
}

/**
 * Format ISO timestamp thành chuỗi tiếng Việt ngắn gọn.
 *
 * @param {string|null|undefined} iso
 * @returns {string}
 */
export function formatTime(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('vi-VN', {
      hour: '2-digit',
      minute: '2-digit',
      day: '2-digit',
      month: '2-digit',
    })
  } catch {
    return ''
  }
}

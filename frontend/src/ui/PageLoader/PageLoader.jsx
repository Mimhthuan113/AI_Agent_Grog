import './PageLoader.css'

/**
 * PageLoader — hiệu ứng load đặc trưng của Aisha.
 * Dùng khi 1 page đang fetch dữ liệu lần đầu hoặc khi chuyển trang nặng.
 *
 * @param {Object} props
 * @param {string} [props.label='Aisha đang chuẩn bị…']  - Text dưới orb
 * @param {'fullscreen'|'inline'} [props.variant='inline']
 *   - fullscreen: bao trùm 100vh, dùng cho boot
 *   - inline:     fit container, dùng cho từng page
 */
export default function PageLoader({
  label = 'Aisha đang chuẩn bị…',
  variant = 'inline',
}) {
  return (
    <div className={`page-loader page-loader--${variant}`} role="status" aria-live="polite">
      <div className="page-loader__stage" aria-hidden>
        {/* Orb chính + 3 vệ tinh quay quanh */}
        <div className="page-loader__orbit">
          <span className="page-loader__satellite page-loader__satellite--1" />
          <span className="page-loader__satellite page-loader__satellite--2" />
          <span className="page-loader__satellite page-loader__satellite--3" />
        </div>
        <div className="page-loader__core">
          <div className="page-loader__core-inner" />
        </div>
      </div>
      <div className="page-loader__label">
        <span>{label}</span>
        <span className="page-loader__dots" aria-hidden>
          <i /><i /><i />
        </span>
      </div>
    </div>
  )
}

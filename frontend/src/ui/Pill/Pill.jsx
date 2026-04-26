import './Pill.css'

/**
 * Aisha Pill — badge / tag / status indicator.
 *
 * @param {Object} props
 * @param {'neutral'|'brand'|'success'|'warn'|'danger'|'info'|'owner'|'guest'} [props.tone='neutral']
 * @param {'sm'|'md'} [props.size='md']
 * @param {boolean} [props.dot]   - Hiện chấm tròn pulse trước label
 * @param {React.ReactNode} [props.icon]
 */
export default function Pill({
  tone = 'neutral',
  size = 'md',
  dot = false,
  icon,
  className = '',
  children,
  ...rest
}) {
  const cls = [
    'ai-pill',
    `ai-pill--${tone}`,
    `ai-pill--${size}`,
    className,
  ].filter(Boolean).join(' ')

  return (
    <span className={cls} {...rest}>
      {dot && <span className="ai-pill__dot" aria-hidden />}
      {icon && <span className="ai-pill__icon" aria-hidden>{icon}</span>}
      <span className="ai-pill__label">{children}</span>
    </span>
  )
}

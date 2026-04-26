import './Button.css'

/**
 * Aisha Button — atom theo Design DNA Aurora.
 *
 * @param {Object} props
 * @param {'primary'|'secondary'|'ghost'|'danger'} [props.variant='primary']
 * @param {'sm'|'md'|'lg'} [props.size='md']
 * @param {boolean} [props.loading]   - Hiện spinner thay icon trái
 * @param {boolean} [props.fullWidth]
 * @param {React.ReactNode} [props.iconLeft]
 * @param {React.ReactNode} [props.iconRight]
 * @param {React.ReactNode} props.children
 */
export default function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  fullWidth = false,
  iconLeft,
  iconRight,
  children,
  className = '',
  disabled,
  type = 'button',
  ...rest
}) {
  const cls = [
    'ai-btn',
    `ai-btn--${variant}`,
    `ai-btn--${size}`,
    fullWidth && 'ai-btn--full',
    loading && 'is-loading',
    className,
  ].filter(Boolean).join(' ')

  return (
    <button
      type={type}
      className={cls}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? (
        <span className="ai-btn__spinner" aria-hidden />
      ) : iconLeft ? (
        <span className="ai-btn__icon">{iconLeft}</span>
      ) : null}
      {children && <span className="ai-btn__label">{children}</span>}
      {iconRight && !loading && <span className="ai-btn__icon">{iconRight}</span>}
    </button>
  )
}

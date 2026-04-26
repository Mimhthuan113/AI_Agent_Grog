import './Card.css'

/**
 * Aisha Card — atom container, dùng cho mọi khối content.
 *
 * @param {Object} props
 * @param {'flat'|'glass'|'elevated'|'aurora'} [props.variant='flat']
 *   - flat: bg-surface + subtle border
 *   - glass: frosted glass (cần overlay aurora ở dưới)
 *   - elevated: shadow card, dùng cho dropdown/modal
 *   - aurora: gradient border + soft glow (highlight card)
 * @param {boolean} [props.interactive] - Có hover effect không
 * @param {boolean} [props.padded=true]  - Padding mặc định var(--space-4)
 */
export default function Card({
  variant = 'flat',
  interactive = false,
  padded = true,
  className = '',
  children,
  ...rest
}) {
  const cls = [
    'ai-card',
    `ai-card--${variant}`,
    interactive && 'ai-card--interactive',
    padded && 'ai-card--padded',
    className,
  ].filter(Boolean).join(' ')

  return (
    <div className={cls} {...rest}>
      {children}
    </div>
  )
}

export function CardHeader({ title, subtitle, action, className = '' }) {
  return (
    <div className={`ai-card__header ${className}`}>
      <div className="ai-card__titles">
        {title    && <h3 className="ai-card__title">{title}</h3>}
        {subtitle && <p  className="ai-card__subtitle">{subtitle}</p>}
      </div>
      {action && <div className="ai-card__action">{action}</div>}
    </div>
  )
}

export function CardBody({ className = '', children }) {
  return <div className={`ai-card__body ${className}`}>{children}</div>
}

export function CardFooter({ className = '', children }) {
  return <div className={`ai-card__footer ${className}`}>{children}</div>
}

import './EmptyState.css'

/**
 * Aisha EmptyState — không bao giờ để screen trống trơn.
 *
 * @param {Object} props
 * @param {React.ReactNode} [props.illustration]  - Mini orb hoặc icon
 * @param {string} props.title
 * @param {string} [props.description]
 * @param {React.ReactNode} [props.action]        - <Button> hoặc nhiều CTA
 * @param {'sm'|'md'|'lg'} [props.size='md']
 */
export default function EmptyState({
  illustration,
  title,
  description,
  action,
  size = 'md',
  className = '',
}) {
  return (
    <div className={`ai-empty ai-empty--${size} ${className}`}>
      <div className="ai-empty__illu" aria-hidden>
        {illustration || <DefaultOrb />}
      </div>
      <h3 className="ai-empty__title">{title}</h3>
      {description && <p className="ai-empty__desc">{description}</p>}
      {action && <div className="ai-empty__action">{action}</div>}
    </div>
  )
}

function DefaultOrb() {
  return <div className="ai-empty__orb" />
}

import { forwardRef, useId, useState } from 'react'
import './Input.css'

/**
 * Aisha Input — floating label, focus = aurora glow underline.
 *
 * @param {Object} props
 * @param {string} [props.label]
 * @param {string} [props.hint]
 * @param {string} [props.error]
 * @param {React.ReactNode} [props.iconLeft]
 * @param {React.ReactNode} [props.iconRight]
 * @param {boolean} [props.fullWidth]
 * @param {'sm'|'md'|'lg'} [props.size='md']
 */
const Input = forwardRef(function Input({
  label,
  hint,
  error,
  iconLeft,
  iconRight,
  fullWidth = true,
  size = 'md',
  className = '',
  id: idProp,
  type = 'text',
  value,
  defaultValue,
  onFocus,
  onBlur,
  ...rest
}, ref) {
  const reactId = useId()
  const id = idProp || `ai-input-${reactId}`
  const [focused, setFocused] = useState(false)

  const hasValue = value != null ? String(value).length > 0 : !!defaultValue
  const floating = focused || hasValue

  const wrapCls = [
    'ai-input',
    `ai-input--${size}`,
    fullWidth && 'ai-input--full',
    focused && 'is-focused',
    error && 'is-error',
    className,
  ].filter(Boolean).join(' ')

  return (
    <div className={wrapCls}>
      {label && (
        <label
          htmlFor={id}
          className={`ai-input__label ${floating ? 'is-floating' : ''} ${iconLeft ? 'has-icon' : ''}`}
        >
          {label}
        </label>
      )}
      <div className="ai-input__field">
        {iconLeft && <span className="ai-input__icon ai-input__icon--left">{iconLeft}</span>}
        <input
          ref={ref}
          id={id}
          type={type}
          value={value}
          defaultValue={defaultValue}
          onFocus={(e) => { setFocused(true); onFocus?.(e) }}
          onBlur={(e)  => { setFocused(false); onBlur?.(e) }}
          aria-invalid={!!error || undefined}
          aria-describedby={hint || error ? `${id}-hint` : undefined}
          {...rest}
        />
        {iconRight && <span className="ai-input__icon ai-input__icon--right">{iconRight}</span>}
      </div>
      {(hint || error) && (
        <p id={`${id}-hint`} className={`ai-input__hint ${error ? 'is-error' : ''}`}>
          {error || hint}
        </p>
      )}
    </div>
  )
})

export default Input

import { useEffect, useState, useCallback } from 'react'

const STORAGE_KEY = 'aisha:theme'
const VALID = ['dark', 'light', 'auto']

/**
 * Theme manager hook.
 * - 'dark'  : force dark
 * - 'light' : force light
 * - 'auto'  : follow OS prefers-color-scheme
 *
 * Persists to localStorage. Sets data-theme attribute on <html>.
 */
export default function useTheme() {
  const [theme, setThemeState] = useState(() => {
    if (typeof window === 'undefined') return 'auto'
    const saved = localStorage.getItem(STORAGE_KEY)
    return VALID.includes(saved) ? saved : 'auto'
  })

  // Apply to root
  useEffect(() => {
    const root = document.documentElement
    if (theme === 'auto') {
      root.removeAttribute('data-theme')
    } else {
      root.setAttribute('data-theme', theme)
    }
  }, [theme])

  const setTheme = useCallback((next) => {
    if (!VALID.includes(next)) return
    localStorage.setItem(STORAGE_KEY, next)
    setThemeState(next)
  }, [])

  /** Cycle: auto → light → dark → auto */
  const cycleTheme = useCallback(() => {
    setThemeState((prev) => {
      const next = prev === 'auto' ? 'light' : prev === 'light' ? 'dark' : 'auto'
      localStorage.setItem(STORAGE_KEY, next)
      return next
    })
  }, [])

  /** Effective theme (resolve 'auto' → dark | light) */
  const effective = theme === 'auto'
    ? (typeof window !== 'undefined' &&
       window.matchMedia('(prefers-color-scheme: light)').matches
       ? 'light' : 'dark')
    : theme

  return { theme, effective, setTheme, cycleTheme }
}

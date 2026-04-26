import { useEffect, useState, useCallback } from 'react'

const STORAGE_KEY = 'aisha:theme'
const VALID = ['dark', 'light']
const DEFAULT_THEME = 'dark'   // Aurora AI — DNA chính là dark

/**
 * Theme manager hook.
 * 2 modes: 'dark' (mặc định, Aurora vibe) | 'light' (bình minh, đọc ngoài nắng).
 *
 * Persists to localStorage. Sets data-theme attribute on <html>.
 */
export default function useTheme() {
  const [theme, setThemeState] = useState(() => {
    if (typeof window === 'undefined') return DEFAULT_THEME
    const saved = localStorage.getItem(STORAGE_KEY)
    return VALID.includes(saved) ? saved : DEFAULT_THEME
  })

  // Apply to root
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const setTheme = useCallback((next) => {
    if (!VALID.includes(next)) return
    localStorage.setItem(STORAGE_KEY, next)
    setThemeState(next)
  }, [])

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark'
      localStorage.setItem(STORAGE_KEY, next)
      return next
    })
  }, [])

  return { theme, setTheme, toggleTheme }
}

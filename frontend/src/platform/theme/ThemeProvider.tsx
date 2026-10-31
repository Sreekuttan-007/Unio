import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { ThemePreference } from '@/ui'
import { useAuth } from '../auth/AuthProvider'

const KEY = 'unio.theme'

function readPreference(): ThemePreference {
  try {
    const stored = window.localStorage.getItem(KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    // storage blocked
  }
  return 'light'
}

interface ThemeContextValue {
  theme: ThemePreference
  setTheme: (theme: ThemePreference) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemePreference>(readPreference)

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
    try {
      window.localStorage.setItem(KEY, theme)
    } catch {
      // storage blocked
    }
  }, [theme])

  const value = useMemo(() => ({ theme, setTheme }), [theme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext)
  if (!context) throw new Error('useTheme must be used inside ThemeProvider')
  return context
}

/** Sets the role accent on the page. The accent name comes from the server, so a role cannot pick its own. */
export function AccentSync() {
  const { bootstrap } = useAuth()
  const accent = bootstrap?.theme.accent ?? 'sky'
  useEffect(() => {
    document.documentElement.setAttribute('data-accent', accent)
  }, [accent])
  return null
}

import { LogOut, Monitor, Moon, Sun } from 'lucide-react'
import { type ReactNode, useEffect, useRef, useState } from 'react'
import { Badge } from '../Badge'
import { Brand } from '../Brand'
import { cn } from '../cn'
import type { ThemePreference } from './types'

export interface TopBarProps {
  roleLabel: string
  userName: string
  userEmail: string
  initials: string
  theme: ThemePreference
  onThemeChange: (theme: ThemePreference) => void
  onSignOut: () => void
  /** Extra controls before the theme switch, such as the notification bell. */
  actions?: ReactNode
}

const NEXT_THEME: Record<ThemePreference, ThemePreference> = { light: 'dark', dark: 'system', system: 'light' }
const THEME_ICON = { light: Sun, dark: Moon, system: Monitor }
const TOP_STYLE = { paddingTop: 'env(safe-area-inset-top)' }

export function TopBar({ roleLabel, userName, userEmail, initials, theme, onThemeChange, onSignOut, actions }: TopBarProps) {
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const ThemeIcon = THEME_ICON[theme]

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent) {
        if (event.key === 'Escape') setOpen(false)
      } else if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  return (
    <header style={TOP_STYLE} className="sticky top-0 z-(--z-top) border-b border-line bg-surface/90 backdrop-blur">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>
      <div className="flex h-(--topbar-height) items-center gap-3 px-4 lg:px-6">
        <Brand />
        <Badge tone="accent" className="hidden sm:inline-flex">{roleLabel}</Badge>
        <div className="flex-1" />
        {actions}
        <button
          type="button"
          aria-label={`Theme: ${theme}. Switch to ${NEXT_THEME[theme]}`}
          onClick={() => onThemeChange(NEXT_THEME[theme])}
          className="grid size-11 place-items-center rounded-full text-muted hover:bg-surface-2 hover:text-ink"
        >
          <ThemeIcon aria-hidden="true" className="size-5" />
        </button>
        <div ref={menuRef} className="relative">
          <button
            type="button"
            aria-haspopup="menu"
            aria-expanded={open}
            aria-label="Account menu"
            data-testid="account-menu"
            onClick={() => setOpen((value) => !value)}
            className="grid size-11 place-items-center rounded-full"
          >
            <span className="grid size-9 place-items-center rounded-full bg-accent text-sm font-semibold text-accent-contrast">{initials}</span>
          </button>
          {open ? (
            <div role="menu" className={cn('absolute right-0 top-full mt-2 w-64 rounded-lg border border-line bg-surface p-2 shadow-pop')}>
              <div className="px-3 py-2">
                <p className="truncate text-sm font-semibold text-ink">{userName}</p>
                <p className="truncate text-xs text-muted">{userEmail}</p>
                <p className="mt-1 text-xs font-medium text-accent-ink">{roleLabel}</p>
              </div>
              <button
                type="button"
                role="menuitem"
                data-testid="sign-out"
                onClick={onSignOut}
                className="flex min-h-11 w-full items-center gap-2 rounded-md px-3 text-sm text-ink hover:bg-surface-2"
              >
                <LogOut aria-hidden="true" className="size-4" />
                Sign out
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  )
}

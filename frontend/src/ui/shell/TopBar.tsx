import { LogOut, Moon, Search, Sun } from 'lucide-react'
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

const TOP_STYLE = { paddingTop: 'env(safe-area-inset-top)' }

export function TopBar({ roleLabel, userName, userEmail, initials, theme, onThemeChange, onSignOut, actions }: TopBarProps) {
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const isDark = theme === 'dark'
  const nextTheme: ThemePreference = isDark ? 'light' : 'dark'

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
    <header style={TOP_STYLE} className="sticky top-0 z-(--z-top) border-b border-line/40 bg-surface/60 shadow-xs backdrop-blur-xl transition-colors">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>
      <div className="flex h-(--topbar-height) items-center gap-3 px-4 lg:px-8">
        <Brand />
        <Badge tone="accent" className="hidden sm:inline-flex">{roleLabel}</Badge>
        
        {/* Flexible spacer pushing controls to the right */}
        <div className="flex-1" />

        {/* Right side controls matching reference layout: [Theme Toggle] -> [Search] -> [Actions] -> [Avatar] */}
        <div className="flex items-center gap-2.5">
          {/* Theme Toggle Switch */}
          <button
            type="button"
            role="switch"
            aria-checked={isDark}
            aria-label={`Theme: ${theme}. Switch to ${nextTheme}`}
            title={`Switch to ${nextTheme} mode`}
            onClick={() => onThemeChange(nextTheme)}
            className={cn(
              'group relative inline-flex h-7 w-12 shrink-0 cursor-pointer items-center rounded-full p-0.5 transition-colors duration-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent select-none',
              isDark
                ? 'bg-accent/90 border border-accent/40 shadow-xs'
                : 'bg-surface-3 border border-border-strong/70 hover:border-border-strong shadow-xs'
            )}
          >
            {/* Background track icons */}
            <span className="pointer-events-none absolute inset-0 flex items-center justify-between px-1.5 text-muted/60">
              <Sun aria-hidden="true" className={cn('size-3.5 transition-opacity duration-200', isDark ? 'opacity-40 text-surface' : 'opacity-0')} />
              <Moon aria-hidden="true" className={cn('size-3.5 transition-opacity duration-200', isDark ? 'opacity-0' : 'opacity-40 text-muted')} />
            </span>

            {/* Sliding Thumb */}
            <span
              className={cn(
                'relative z-10 flex size-6 items-center justify-center rounded-full shadow-sm transition-transform duration-300 ease-out',
                isDark
                  ? 'translate-x-5 bg-surface text-accent'
                  : 'translate-x-0 bg-surface text-amber-500'
              )}
            >
              {isDark ? (
                <Moon aria-hidden="true" className="size-3.5 fill-accent/20 stroke-[2.2] transition-transform duration-300 -rotate-12" />
              ) : (
                <Sun aria-hidden="true" className="size-3.5 fill-amber-400/20 stroke-[2.2] transition-transform duration-300 rotate-0" />
              )}
            </span>
          </button>

          <button
            type="button"
            aria-label="Search"
            className="grid size-10 place-items-center rounded-full border border-line/60 bg-surface/75 text-muted shadow-xs backdrop-blur-md transition-colors hover:bg-surface-2 hover:text-ink"
          >
            <Search aria-hidden="true" className="size-4" />
          </button>

          {actions}

          <div ref={menuRef} className="relative">
            <button
              type="button"
              aria-haspopup="menu"
              aria-expanded={open}
              aria-label="Account menu"
              data-testid="account-menu"
              onClick={() => setOpen((value) => !value)}
              className="grid size-10 place-items-center rounded-full ring-2 ring-line/80 transition-transform hover:scale-105 active:scale-95"
            >
              <span className="grid size-9 place-items-center rounded-full bg-accent text-xs font-semibold text-accent-contrast shadow-sm">
                {initials}
              </span>
            </button>
            {open ? (
              <div role="menu" className={cn('absolute right-0 top-full mt-2 w-64 rounded-xl border border-line bg-surface/90 p-2 shadow-pop backdrop-blur-xl')}>
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
                  className="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 text-sm text-ink hover:bg-surface-2"
                >
                  <LogOut aria-hidden="true" className="size-4" />
                  Sign out
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </header>
  )
}

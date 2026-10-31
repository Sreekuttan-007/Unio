import { CornerDownLeft } from 'lucide-react'
import { useState, useEffect } from 'react'
import { NavIcon } from '../icons'
import { cn } from '../cn'
import { isActivePath, type NavEntryView } from './types'

export interface SideNavProps {
  items: NavEntryView[]
  activePath: string
  roleLabel?: string
  onNavigate: (path: string) => void
}

const PINNED_STORAGE_KEY = 'unio.sidebar.pinned'

/** Desktop floating glassmorphism navigation rail. Compact by default, expands on hover, can be fixed open. */
export function SideNav({ items, activePath, onNavigate }: SideNavProps) {
  const [isPinned, setIsPinned] = useState(() => {
    try {
      return window.localStorage.getItem(PINNED_STORAGE_KEY) === 'true'
    } catch {
      return false
    }
  })

  useEffect(() => {
    try {
      window.localStorage.setItem(PINNED_STORAGE_KEY, String(isPinned))
    } catch {
      // storage unavailable
    }
  }, [isPinned])

  return (
    <aside
      aria-label="Main"
      className={cn(
        'fixed inset-y-0 left-0 z-(--z-nav) hidden flex-col items-center px-2.5 pb-6 pt-[calc(var(--topbar-height)+1rem)] transition-[width] duration-300 ease-in-out lg:flex',
        isPinned ? 'w-64' : 'group/sidebar w-20 hover:w-64',
      )}
    >
      {/* Floating glassmorphism navigation rail container */}
      <nav className="flex flex-1 w-full flex-col justify-between overflow-hidden rounded-3xl border border-line/50 bg-surface/80 p-2 shadow-card backdrop-blur-xl transition-all">
        <div className="no-scrollbar space-y-2 overflow-y-auto overflow-x-hidden">
          {items.map((item) => {
            const active = isActivePath(activePath, item.path)
            return (
              <a
                key={item.key}
                href={item.path}
                aria-current={active ? 'page' : undefined}
                data-testid={`nav-${item.key}`}
                onClick={(event) => {
                  event.preventDefault()
                  onNavigate(item.path)
                }}
                className={cn(
                  'group/item flex h-11 w-full items-center rounded-2xl transition-all',
                  active
                    ? 'text-accent-ink font-semibold'
                    : 'text-muted hover:text-ink',
                )}
              >
                <span
                  className={cn(
                    'grid size-10 shrink-0 place-items-center rounded-2xl transition-all',
                    isPinned
                      ? 'mx-0 mr-3'
                      : 'mx-auto group-hover/sidebar:mx-0 group-hover/sidebar:mr-3',
                    active
                      ? 'bg-ink text-surface shadow-xs'
                      : 'text-muted group-hover/item:text-ink group-hover/item:bg-surface-2',
                  )}
                >
                  <NavIcon name={item.icon} className="size-5 shrink-0" />
                </span>
                <span
                  className={cn(
                    'min-w-0 flex-1 truncate text-sm font-medium transition-all duration-300',
                    isPinned
                      ? 'opacity-100 max-w-xs'
                      : 'opacity-0 max-w-0 overflow-hidden group-hover/sidebar:max-w-xs group-hover/sidebar:opacity-100',
                  )}
                >
                  {item.label}
                </span>
                {item.badge ? (
                  <span
                    className={cn(
                      'rounded-full px-2 py-0.5 text-xs font-semibold shrink-0 ml-auto transition-all duration-300',
                      isPinned
                        ? 'opacity-100 max-w-xs'
                        : 'opacity-0 max-w-0 overflow-hidden group-hover/sidebar:max-w-xs group-hover/sidebar:opacity-100',
                      active ? 'bg-accent text-accent-contrast' : 'bg-surface-3 text-muted',
                    )}
                  >
                    {item.badge}
                  </span>
                ) : null}
              </a>
            )
          })}
        </div>

        {/* Bottom corner action button - clicking fixes/pins the sidebar open instead of reducing it */}
        <div
          className={cn(
            'flex items-center border-t border-line/40 pt-2 transition-all',
            isPinned
              ? 'justify-end pr-1'
              : 'justify-center group-hover/sidebar:justify-end group-hover/sidebar:pr-1',
          )}
        >
          <button
            type="button"
            aria-label={isPinned ? 'Collapse sidebar' : 'Fix sidebar open'}
            title={isPinned ? 'Collapse sidebar' : 'Fix sidebar open'}
            onClick={() => setIsPinned((prev) => !prev)}
            className={cn(
              'grid size-10 shrink-0 place-items-center rounded-full border border-line/60 bg-surface/90 text-muted shadow-xs backdrop-blur-sm transition-all hover:scale-105 hover:bg-surface-2 hover:text-ink active:scale-95',
              isPinned && 'bg-accent-soft text-accent-ink border-accent/40 shadow-sm',
            )}
          >
            <CornerDownLeft
              aria-hidden="true"
              className={cn('size-4 transition-transform duration-300', isPinned && 'rotate-180 text-accent-ink')}
            />
          </button>
        </div>
      </nav>
    </aside>
  )
}

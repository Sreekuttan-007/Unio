import { Ellipsis, X } from 'lucide-react'
import { useState } from 'react'
import { NavIcon } from '../icons'
import { cn } from '../cn'
import { isActivePath, type NavEntryView } from './types'

export interface BottomNavProps {
  items: NavEntryView[]
  activePath: string
  onNavigate: (path: string) => void
  /** How many items sit on the bar before the rest move into the More sheet. */
  maxOnBar?: number
}

const BAR_STYLE = { paddingBottom: 'env(safe-area-inset-bottom)' }

/** Phone navigation. Five or fewer items all sit on the bar, otherwise the rest go under More. */
export function BottomNav({ items, activePath, onNavigate, maxOnBar = 5 }: BottomNavProps) {
  const [moreOpen, setMoreOpen] = useState(false)
  const overflow = items.length > maxOnBar
  const onBar = overflow ? items.slice(0, maxOnBar - 1) : items
  const more = overflow ? items.slice(maxOnBar - 1) : []
  const moreActive = more.some((item) => isActivePath(activePath, item.path))

  const go = (path: string) => {
    setMoreOpen(false)
    onNavigate(path)
  }

  return (
    <>
      <nav
        aria-label="Main"
        style={BAR_STYLE}
        className="fixed inset-x-0 bottom-0 z-(--z-nav) border-t border-line bg-surface lg:hidden"
      >
        <ul className="mx-auto flex max-w-xl items-stretch justify-around">
          {onBar.map((item) => {
            const active = isActivePath(activePath, item.path)
            return (
              <li key={item.key} className="min-w-0 flex-1">
                <button
                  type="button"
                  aria-current={active ? 'page' : undefined}
                  data-testid={`bottomnav-${item.key}`}
                  onClick={() => go(item.path)}
                  className={cn(
                    'relative flex min-h-(--bottomnav-height) w-full flex-col items-center justify-center gap-1 px-1 text-xs font-medium',
                    active ? 'text-accent-ink' : 'text-muted',
                  )}
                >
                  <span className={cn('relative grid h-8 w-14 place-items-center rounded-full', active && 'bg-accent-soft')}>
                    <NavIcon name={item.icon} className="size-5" />
                    {item.badge ? (
                      <span className="absolute -right-0.5 -top-0.5 min-w-4 rounded-full bg-accent px-1 text-center text-[0.625rem] font-semibold leading-4 text-accent-contrast">
                        {item.badge}
                      </span>
                    ) : null}
                  </span>
                  <span className="w-full truncate text-center">{item.label}</span>
                </button>
              </li>
            )
          })}
          {overflow ? (
            <li className="min-w-0 flex-1">
              <button
                type="button"
                aria-haspopup="dialog"
                aria-expanded={moreOpen}
                onClick={() => setMoreOpen(true)}
                className={cn(
                  'flex min-h-(--bottomnav-height) w-full flex-col items-center justify-center gap-1 px-1 text-xs font-medium',
                  moreActive ? 'text-accent-ink' : 'text-muted',
                )}
              >
                <span className={cn('grid h-8 w-14 place-items-center rounded-full', moreActive && 'bg-accent-soft')}>
                  <Ellipsis aria-hidden="true" className="size-5" />
                </span>
                More
              </button>
            </li>
          ) : null}
        </ul>
      </nav>

      {moreOpen ? (
        <div className="fixed inset-0 z-(--z-overlay) lg:hidden" role="dialog" aria-modal="true" aria-label="More screens">
          <button type="button" aria-label="Close" className="absolute inset-0 bg-ink/40" onClick={() => setMoreOpen(false)} />
          <div style={BAR_STYLE} className="absolute inset-x-0 bottom-0 max-h-[80dvh] overflow-y-auto rounded-t-lg border-t border-line bg-surface p-4 shadow-pop">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-base font-semibold text-ink">More</h2>
              <button type="button" aria-label="Close" onClick={() => setMoreOpen(false)} className="grid size-11 place-items-center rounded-full hover:bg-surface-2">
                <X aria-hidden="true" className="size-5" />
              </button>
            </div>
            <ul className="space-y-1">
              {more.map((item) => (
                <li key={item.key}>
                  <button
                    type="button"
                    data-testid={`bottomnav-${item.key}`}
                    onClick={() => go(item.path)}
                    className={cn(
                      'flex min-h-11 w-full items-center gap-3 rounded-md px-3 text-sm font-medium',
                      isActivePath(activePath, item.path) ? 'bg-accent-soft text-accent-ink' : 'text-ink hover:bg-surface-2',
                    )}
                  >
                    <NavIcon name={item.icon} className="size-5" />
                    {item.label}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </>
  )
}

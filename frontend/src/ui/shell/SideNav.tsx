import { NavIcon } from '../icons'
import { cn } from '../cn'
import { isActivePath, type NavEntryView } from './types'

export interface SideNavProps {
  items: NavEntryView[]
  activePath: string
  roleLabel: string
  onNavigate: (path: string) => void
}

/** Desktop navigation. It only maps over the items it is given, with no role logic at all. */
export function SideNav({ items, activePath, roleLabel, onNavigate }: SideNavProps) {
  return (
    <aside
      aria-label="Main"
      className="fixed inset-y-0 left-0 z-(--z-nav) hidden w-(--nav-width) flex-col border-r border-line bg-surface pt-(--topbar-height) lg:flex"
    >
      <p className="px-5 pb-2 pt-5 text-xs font-semibold uppercase tracking-wide text-faint">{roleLabel}</p>
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-6">
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
                'flex min-h-11 items-center gap-3 rounded-md px-3 text-sm font-medium transition-colors',
                active ? 'bg-accent-soft text-accent-ink' : 'text-muted hover:bg-surface-2 hover:text-ink',
              )}
            >
              <NavIcon name={item.icon} className="size-5 shrink-0" />
              <span className="min-w-0 flex-1 truncate">{item.label}</span>
              {item.badge ? (
                <span className="rounded-full bg-accent px-2 py-0.5 text-xs font-semibold text-accent-contrast">{item.badge}</span>
              ) : null}
            </a>
          )
        })}
      </nav>
    </aside>
  )
}

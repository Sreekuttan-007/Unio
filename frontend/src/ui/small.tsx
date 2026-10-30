import { CircleAlert, CircleCheck, Info, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from './cn'
import type { Tone } from './Badge'

export function Avatar({ initials, size = 'md', className }: { initials: string; size?: 'sm' | 'md' | 'lg'; className?: string }) {
  const sizes = { sm: 'size-7 text-xs', md: 'size-9 text-sm', lg: 'size-12 text-base' }
  return (
    <span aria-hidden="true" className={cn('grid shrink-0 place-items-center rounded-full bg-accent-soft font-semibold text-accent-ink', sizes[size], className)}>
      {initials}
    </span>
  )
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
  label: string
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex max-w-full overflow-x-auto rounded-md border border-line-strong bg-surface-2 p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
          className={cn(
            'min-h-10 whitespace-nowrap rounded-sm px-3 text-sm font-medium transition-colors',
            option.value === value ? 'bg-surface text-ink shadow-card' : 'text-muted hover:text-ink',
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

const BANNER: Record<Exclude<Tone, 'neutral' | 'accent'>, { box: string; icon: typeof Info }> = {
  info: { box: 'bg-info-soft text-info-ink', icon: Info },
  success: { box: 'bg-success-soft text-success-ink', icon: CircleCheck },
  warning: { box: 'bg-warning-soft text-warning-ink', icon: TriangleAlert },
  danger: { box: 'bg-danger-soft text-danger-ink', icon: CircleAlert },
}

export function Banner({
  tone = 'info',
  title,
  children,
  action,
  role,
}: {
  tone?: keyof typeof BANNER
  title: string
  children?: ReactNode
  action?: ReactNode
  role?: 'alert' | 'status'
}) {
  const { box, icon: Icon } = BANNER[tone]
  return (
    <div role={role} className={cn('flex flex-wrap items-start gap-3 rounded-lg px-4 py-3', box)}>
      <Icon aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">{title}</p>
        {children ? <div className="mt-0.5 text-sm opacity-90">{children}</div> : null}
      </div>
      {action}
    </div>
  )
}

export function ListRow({
  leading,
  title,
  subtitle,
  meta,
  trailing,
  onClick,
  selected,
  testId,
}: {
  leading?: ReactNode
  title: ReactNode
  subtitle?: ReactNode
  meta?: ReactNode
  trailing?: ReactNode
  onClick?: () => void
  selected?: boolean
  testId?: string
}) {
  const body = (
    <>
      {leading}
      <span className="min-w-0 flex-1 text-left">
        <span className="block truncate text-sm font-medium text-ink">{title}</span>
        {subtitle ? <span className="block truncate text-xs text-muted">{subtitle}</span> : null}
      </span>
      {meta ? <span className="shrink-0 text-xs text-muted">{meta}</span> : null}
      {trailing}
    </>
  )
  const cls = cn(
    'flex min-h-14 w-full items-center gap-3 border-b border-line px-4 py-2 last:border-0',
    onClick && 'hover:bg-surface-2',
    selected && 'bg-accent-soft',
  )
  return onClick ? (
    <button type="button" onClick={onClick} aria-pressed={selected} data-testid={testId} className={cls}>
      {body}
    </button>
  ) : (
    <div data-testid={testId} className={cls}>
      {body}
    </div>
  )
}

export function Toggle({ checked, onChange, label, description }: { checked: boolean; onChange: (checked: boolean) => void; label: string; description?: string }) {
  return (
    <label className="flex min-h-11 cursor-pointer items-center justify-between gap-4">
      <span className="min-w-0">
        <span className="block text-sm font-medium text-ink">{label}</span>
        {description ? <span className="block text-xs text-muted">{description}</span> : null}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={cn('relative h-7 w-12 shrink-0 rounded-full transition-colors', checked ? 'bg-accent' : 'bg-line-strong')}
      >
        <span className={cn('absolute left-0.5 top-0.5 size-6 rounded-full bg-surface shadow-card transition-transform', checked && 'translate-x-5')} />
      </button>
    </label>
  )
}

export function TextArea({ label, hint, className, ...rest }: { label: string; hint?: string } & React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = rest.id ?? `ta-${label.replace(/\s+/g, '-').toLowerCase()}`
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-sm font-medium text-ink">{label}</label>
      <textarea
        id={id}
        className={cn('min-h-28 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-faint', className)}
        {...rest}
      />
      {hint ? <p className="text-xs text-muted">{hint}</p> : null}
    </div>
  )
}

import { cn } from './cn'

export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" role="img" aria-label="UNIO" className={cn('size-8', className)}>
      <rect width="64" height="64" rx="16" className="fill-ink" />
      <path d="M18 16v20a14 14 0 0 0 28 0V16" fill="none" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" className="stroke-accent" />
      <circle cx="32" cy="50" r="3.5" className="fill-accent-contrast" />
    </svg>
  )
}

export function Brand({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <BrandMark />
      <span className="text-lg font-semibold tracking-tight text-ink">UNIO</span>
    </span>
  )
}

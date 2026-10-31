import { cn } from './cn'

export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" role="img" aria-label="UNIO" className={cn('size-8 shrink-0', className)}>
      {/* Concentric orbital swirl matching reference brand mark */}
      <circle cx="32" cy="32" r="4.5" className="fill-ink" />
      <path
        d="M24 33 A 9 9 0 0 1 38 24 A 11 11 0 0 1 44 33"
        fill="none"
        strokeWidth="3.2"
        strokeLinecap="round"
        className="stroke-ink"
      />
      <path
        d="M17 35 A 16 16 0 0 1 36 16 A 18 18 0 0 1 51 31"
        fill="none"
        strokeWidth="3.2"
        strokeLinecap="round"
        className="stroke-ink"
      />
      <path
        d="M11 34 A 22 22 0 0 1 35 10 A 24 24 0 0 1 57 27"
        fill="none"
        strokeWidth="3.2"
        strokeLinecap="round"
        className="stroke-ink"
      />
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

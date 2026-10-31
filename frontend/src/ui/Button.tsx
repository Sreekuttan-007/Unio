import { Loader2 } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from './cn'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'glass'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-accent text-accent-contrast hover:bg-accent-hover shadow-sm',
  secondary: 'bg-surface text-ink border border-line hover:bg-surface-2 shadow-xs',
  ghost: 'bg-transparent text-ink hover:bg-surface-2',
  danger: 'bg-danger text-accent-contrast hover:opacity-90 shadow-sm',
  glass: 'btn-glass text-ink border border-line/50 hover:border-line shadow-sm',
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  compact?: boolean
  loading?: boolean
  icon?: ReactNode
}

export function Button({
  variant = 'primary',
  compact = false,
  loading = false,
  icon,
  className,
  disabled,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        'inline-flex min-h-11 items-center justify-center gap-2 rounded-xl font-medium transition-all active:scale-98',
        'disabled:cursor-not-allowed disabled:opacity-55',
        compact ? 'min-h-9 px-3.5 text-xs' : 'px-5 text-sm',
        VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 aria-hidden="true" className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  )
}

export interface GlossButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children?: ReactNode
}

/**
 * Responsive gloss glassmorphism button component with dual-axis specular reflection,
 * dynamic conic light rim, ambient diffuse drop shadow, and 3D active state.
 */
export function GlossButton({
  children = 'Generate',
  className,
  type = 'button',
  disabled,
  ...rest
}: GlossButtonProps) {
  return (
    <div className={cn('button-wrap', className)}>
      <button type={type} disabled={disabled} {...rest}>
        <span>{children}</span>
      </button>
      <div className="button-shadow" />
    </div>
  )
}

export const GlassButton = GlossButton
export type GlassStartButtonProps = GlossButtonProps
export const GlassStartButton = GlossButton

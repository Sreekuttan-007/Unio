import { ArrowRight, GitMerge, ScrollText, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { BrandMark } from './Brand'
import { TextField } from './fields'
import { WakingBanner } from './states'

export interface DemoAccountView {
  email: string
  name: string
  roleLabel: string
  accent: string
}

export interface LoginCardProps {
  demoAccounts: DemoAccountView[]
  /** The demo account being signed in, so only that chip shows a spinner. */
  busyEmail: string | null
  submitting: boolean
  error: string | null
  waking: boolean
  onDemoLogin: (email: string) => void
  onSubmit: (email: string, password: string) => void
}

const PROMISES = [
  { icon: GitMerge, title: 'One report, one incident' },
  { icon: ShieldCheck, title: 'Conflicts stop before they happen' },
  { icon: ScrollText, title: 'Every decision is on the record' },
]

const initials = (name: string) => name.split(' ').filter((part) => /^[A-Za-z]/.test(part)).map((part) => part[0]).join('').slice(0, 2).toUpperCase()

export function LoginCard({ demoAccounts, busyEmail, submitting, error, waking, onDemoLogin, onSubmit }: LoginCardProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mousePos, setMousePos] = useState({ x: 50, y: 50 })
  const anyBusy = submitting || busyEmail !== null

  const handleMouseMove = (e: React.MouseEvent<HTMLElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = Math.round(((e.clientX - rect.left) / rect.width) * 100)
    const y = Math.round(((e.clientY - rect.top) / rect.height) * 100)
    setMousePos({ x, y })
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    onSubmit(email, password)
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside
        onMouseMove={handleMouseMove}
        style={{ '--mouse-x': `${mousePos.x}%`, '--mouse-y': `${mousePos.y}%` } as React.CSSProperties}
        className="relative hidden overflow-hidden bg-ink p-12 text-bg lg:flex lg:flex-col lg:justify-between select-none"
      >
        {/* Dynamic cursor-following radial gradient glow and illuminated mesh grid */}
        <div aria-hidden="true" className="interactive-grid-base" />
        <div aria-hidden="true" className="interactive-grid-glow" />
        <div aria-hidden="true" className="interactive-gradient-spotlight" />
        <div aria-hidden="true" className="interactive-ambient-orb-1" />
        <div aria-hidden="true" className="interactive-ambient-orb-2" />

        <div className="relative z-10 flex items-center gap-4">
          <BrandMark className="size-15" />
          <span className="text-3xl font-bold tracking-tight text-white">UNIO</span>
        </div>
        <div className="relative z-10 max-w-md space-y-8">
          <h2 className="text-4xl font-semibold leading-tight tracking-tight">Campus operations that fix the problem, not just log it.</h2>
          <ul className="space-y-4">
            {PROMISES.map(({ icon: Icon, title }) => (
              <li key={title} className="flex items-center gap-3.5">
                <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-surface/10 text-white backdrop-blur-xs">
                  <Icon aria-hidden="true" className="size-4.5" />
                </span>
                <span className="font-medium text-base text-bg">{title}</span>
              </li>
            ))}
          </ul>
        </div>
        {/* Clean bottom anchor */}
        <div className="relative z-10" />
      </aside>

      <main className="flex items-center justify-center px-5 py-10">
        <div className="w-full max-w-md space-y-6">
          <div className="space-y-2 lg:hidden">
            <div className="flex items-center gap-3"><BrandMark className="size-11" /><span className="text-2xl font-bold tracking-tight text-ink">UNIO</span></div>
          </div>
          <div className="space-y-1.5">
            <h1 className="text-3xl font-semibold tracking-tight text-ink">Welcome back</h1>
            <p className="text-sm text-muted">Sign in to your campus workspace.</p>
          </div>

          {waking ? <WakingBanner /> : null}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <TextField label="Email" type="email" autoComplete="username" inputMode="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            <TextField label="Password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
            {error ? <p role="alert" data-testid="login-error" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-ink">{error}</p> : null}
            <div className="button-wrap relative z-10 w-full rounded-full bg-transparent">
              <button
                type="submit"
                disabled={anyBusy || !email || !password}
                className="glass-button glass-button-primary relative z-30 flex w-full cursor-pointer items-center justify-center rounded-full py-3 text-center outline-none focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 disabled:transform-none"
              >
                <span className="button-text relative z-10 block select-none text-base font-semibold tracking-tight text-white">
                  {submitting ? 'Signing in...' : 'Sign in'}
                </span>
                <div className="button-shine" />
              </button>
            </div>
          </form>

          {demoAccounts.length > 0 ? (
            <section aria-labelledby="demo-heading" className="space-y-3">
              <div className="flex items-center gap-3">
                <span className="h-px flex-1 bg-line" />
                <h2 id="demo-heading" className="text-xs font-semibold uppercase tracking-wide text-muted">Or explore as</h2>
                <span className="h-px flex-1 bg-line" />
              </div>
              <ul className="grid grid-cols-1 gap-2.5 min-[26rem]:grid-cols-2">
                {demoAccounts.map((account) => (
                  <li key={account.email}>
                    {/* data-accent scopes the role colour to this chip, so each role shows its own */}
                    <button
                      type="button"
                      data-accent={account.accent}
                      data-testid={`demo-${account.email}`}
                      disabled={anyBusy}
                      onClick={() => onDemoLogin(account.email)}
                      className="group flex min-h-16 w-full items-center gap-3 rounded-2xl border border-line/70 bg-surface/90 px-3.5 py-2.5 text-left shadow-card backdrop-blur-xs transition hover:-translate-y-px hover:border-accent hover:shadow-pop disabled:opacity-60"
                    >
                      <span aria-hidden="true" className="grid size-10 shrink-0 place-items-center rounded-full bg-accent text-sm font-semibold text-accent-contrast">{initials(account.name)}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-semibold leading-tight text-ink">{account.roleLabel}</span>
                        <span className="block truncate text-xs text-muted">{account.name}</span>
                      </span>
                      <ArrowRight aria-hidden="true" className="size-4 shrink-0 text-faint transition group-hover:translate-x-0.5 group-hover:text-accent-ink" />
                      {busyEmail === account.email ? <span className="sr-only">Signing in</span> : null}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      </main>
    </div>
  )
}

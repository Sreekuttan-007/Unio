import { ArrowRight, GitMerge, ScrollText, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { BrandMark } from './Brand'
import { Button } from './Button'
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
  { icon: GitMerge, title: 'One report, one incident', text: 'Fourteen people report the same outage and it becomes one problem with one status.' },
  { icon: ShieldCheck, title: 'Conflicts stop before they happen', text: 'Double bookings, wrong technicians and self-approval are refused with a reason.' },
  { icon: ScrollText, title: 'Every decision is on the record', text: 'Who did what, when and why, from the first report to closure.' },
]

const initials = (name: string) => name.split(' ').filter((part) => /^[A-Za-z]/.test(part)).map((part) => part[0]).join('').slice(0, 2).toUpperCase()

export function LoginCard({ demoAccounts, busyEmail, submitting, error, waking, onDemoLogin, onSubmit }: LoginCardProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const anyBusy = submitting || busyEmail !== null

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    onSubmit(email, password)
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="relative hidden overflow-hidden bg-ink p-12 text-bg lg:flex lg:flex-col lg:justify-between">
        <div aria-hidden="true" className="pointer-events-none absolute -right-32 -top-32 size-[28rem] rounded-full bg-accent opacity-25 blur-3xl" />
        <div aria-hidden="true" className="pointer-events-none absolute -bottom-40 -left-24 size-[26rem] rounded-full bg-info opacity-20 blur-3xl" />
        <div className="relative flex items-center gap-3">
          <BrandMark className="size-10" />
          <span className="text-xl font-semibold tracking-tight">UNIO</span>
        </div>
        <div className="relative max-w-md space-y-8">
          <h2 className="text-4xl font-semibold leading-tight tracking-tight">Campus operations that fix the problem, not just log it.</h2>
          <ul className="space-y-5">
            {PROMISES.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-4">
                <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-surface/10"><Icon aria-hidden="true" className="size-5" /></span>
                <span><span className="block font-medium">{title}</span><span className="block text-sm opacity-70">{text}</span></span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-sm opacity-60">A fictional campus. All names, rooms and numbers are invented for the demo.</p>
      </aside>

      <main className="flex items-center justify-center px-5 py-10">
        <div className="w-full max-w-md space-y-6">
          <div className="space-y-2 lg:hidden">
            <div className="flex items-center gap-2.5"><BrandMark /><span className="text-lg font-semibold tracking-tight text-ink">UNIO</span></div>
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
            <Button type="submit" className="w-full" loading={submitting} disabled={anyBusy || !email || !password}>Sign in</Button>
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
                      className="group flex min-h-16 w-full items-center gap-3 rounded-lg border border-line bg-surface px-3 py-2 text-left shadow-card transition hover:-translate-y-px hover:border-accent hover:shadow-pop disabled:opacity-60"
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

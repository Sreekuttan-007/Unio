import { ArrowRight } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Brand } from './Brand'
import { Button } from './Button'
import { Card } from './Card'
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

export function LoginCard({ demoAccounts, busyEmail, submitting, error, waking, onDemoLogin, onSubmit }: LoginCardProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const anyBusy = submitting || busyEmail !== null

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    onSubmit(email, password)
  }

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-md flex-col justify-center gap-5 px-4 py-10">
      <div className="flex flex-col items-center gap-2 text-center">
        <Brand />
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Sign in to your campus workspace</h1>
        <p className="text-sm text-muted">Report once. Understand the impact. Validate the response. Track it to closure.</p>
      </div>

      {waking ? <WakingBanner /> : null}

      <Card className="space-y-4 p-5">
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <TextField label="Email" type="email" autoComplete="username" inputMode="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          <TextField label="Password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          {error ? (
            <p role="alert" data-testid="login-error" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-ink">{error}</p>
          ) : null}
          <Button type="submit" className="w-full" loading={submitting} disabled={anyBusy || !email || !password}>
            Sign in
          </Button>
        </form>
      </Card>

      {demoAccounts.length > 0 ? (
        <section aria-labelledby="demo-heading" className="space-y-3">
          <h2 id="demo-heading" className="text-center text-xs font-semibold uppercase tracking-wide text-muted">
            Demo: tap a role to explore
          </h2>
          <ul className="grid grid-cols-1 gap-2 min-[26rem]:grid-cols-2">
            {demoAccounts.map((account) => (
              <li key={account.email}>
                {/* data-accent scopes the role accent to this chip, so each shows its own colour */}
                <button
                  type="button"
                  data-accent={account.accent}
                  data-testid={`demo-${account.email}`}
                  disabled={anyBusy}
                  onClick={() => onDemoLogin(account.email)}
                  className="flex min-h-14 w-full items-center gap-3 rounded-md border border-line bg-surface px-3 text-left transition-colors hover:border-accent hover:bg-accent-soft disabled:opacity-60"
                >
                  <span aria-hidden="true" className="size-3 shrink-0 rounded-full bg-accent" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-ink">{account.roleLabel}</span>
                    <span className="block truncate text-xs text-muted">{account.name}</span>
                  </span>
                  <ArrowRight aria-hidden="true" className="size-4 shrink-0 text-faint" />
                  {busyEmail === account.email ? <span className="sr-only">Signing in</span> : null}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '@/platform/api/client'
import type { DemoAccount } from '@/platform/api/types'
import { useAuth } from '@/platform/auth/AuthProvider'
import { useServerStatus } from '@/platform/useServerStatus'
import { LoginCard, OfflineState } from '@/ui'
import { describeError } from '../shared/errors'

export function LoginScreen() {
  const { signInWithPassword, signInDemo } = useAuth()
  const { waking, reachable } = useServerStatus()
  const [busyEmail, setBusyEmail] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const role = params.get('role')?.toLowerCase()
    if (role === 'student') {
      void signInDemo('student@unio.demo')
    }
  }, [signInDemo])

  // The server mounts this list only in demo mode, so a 404 simply means no demo chips.
  const demo = useQuery({
    queryKey: ['demo-accounts'],
    queryFn: () => api<DemoAccount[]>('/auth/demo-accounts', { auth: false }),
    enabled: reachable === true,
    retry: false,
  })

  if (reachable === false) {
    return (
      <div className="grid min-h-dvh place-items-center p-4">
        <OfflineState onRetry={() => window.location.reload()} />
      </div>
    )
  }

  const run = async (action: () => Promise<void>, start: () => void, stop: () => void) => {
    setError(null)
    start()
    try {
      await action()
    } catch (failure) {
      setError(describeError(failure))
      stop()
    }
  }

  return (
    <LoginCard
      demoAccounts={(demo.data ?? []).map((account) => ({
        email: account.email,
        name: account.name,
        roleLabel: account.roleLabel,
        accent: account.accent,
      }))}
      busyEmail={busyEmail}
      submitting={submitting}
      error={error}
      waking={waking}
      onDemoLogin={(email) => void run(() => signInDemo(email), () => setBusyEmail(email), () => setBusyEmail(null))}
      onSubmit={(email, password) =>
        void run(() => signInWithPassword(email, password), () => setSubmitting(true), () => setSubmitting(false))
      }
    />
  )
}

import { CloudOff, Inbox, Lock, ServerCog, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from './Button'
import { Card } from './Card'

function StateCard({ icon, title, description, action }: { icon: ReactNode; title: string; description?: string; action?: ReactNode }) {
  return (
    <Card className="mx-auto flex max-w-lg flex-col items-center gap-3 rounded-2xl border border-line bg-surface p-10 text-center shadow-card">
      <div className="grid size-12 place-items-center rounded-full bg-accent-soft text-accent-ink ring-4 ring-surface shadow-xs">{icon}</div>
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      {description ? <p className="text-sm text-muted">{description}</p> : null}
      {action}
    </Card>
  )
}

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return <StateCard icon={<Inbox aria-hidden="true" className="size-6" />} title={title} description={description} action={action} />
}

export function ErrorState({ title = 'Something went wrong', description, onRetry }: { title?: string; description?: string; onRetry?: () => void }) {
  return (
    <div role="alert">
      <StateCard
        icon={<TriangleAlert aria-hidden="true" className="size-6" />}
        title={title}
        description={description}
        action={onRetry ? <Button variant="secondary" onClick={onRetry}>Try again</Button> : undefined}
      />
    </div>
  )
}

export function NotPermitted({ onHome }: { onHome?: () => void }) {
  return (
    <StateCard
      icon={<Lock aria-hidden="true" className="size-6" />}
      title="This is not part of your workspace"
      description="Your role does not include this screen. Nothing was loaded for it."
      action={onHome ? <Button variant="secondary" onClick={onHome}>Back to my workspace</Button> : undefined}
    />
  )
}

export function OfflineState({ onRetry }: { onRetry?: () => void }) {
  return (
    <div role="alert">
      <StateCard
        icon={<CloudOff aria-hidden="true" className="size-6" />}
        title="Cannot reach the server"
        description="Check your connection. The server may also be starting up, which can take up to a minute."
        action={onRetry ? <Button variant="secondary" onClick={onRetry}>Retry</Button> : undefined}
      />
    </div>
  )
}

/** Shown while a sleeping host wakes up, so a slow first load reads as expected, not broken. */
export function WakingBanner() {
  return (
    <div role="status" className="flex items-center gap-2 rounded-md bg-info-soft px-3 py-2 text-sm text-info-ink">
      <ServerCog aria-hidden="true" className="size-4 shrink-0" />
      Waking the server. This can take up to a minute on the first visit.
    </div>
  )
}

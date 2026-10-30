import { Hammer } from 'lucide-react'
import type { ReactNode } from 'react'
import { Badge } from './Badge'
import { Card, CardBody } from './Card'
import { PageHeader } from './PageHeader'

export interface PlannedScreenProps {
  title: string
  summary: string
  phase: number
  /** Requirement ids from docs/PS_LOCK.md, such as M5. */
  requirements?: string[]
  /** What this screen will show, in plain words. */
  highlights?: string[]
  children?: ReactNode
}

/** The honest placeholder for a screen that a later phase builds. */
export function PlannedScreen({ title, summary, phase, requirements = [], highlights = [], children }: PlannedScreenProps) {
  return (
    <div>
      <PageHeader title={title} description={summary} />
      {children}
      <Card>
        <CardBody className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="warning" icon={<Hammer aria-hidden="true" className="size-3" />}>Arrives in Phase {phase}</Badge>
            {requirements.map((requirement) => (
              <Badge key={requirement} tone="accent">{requirement}</Badge>
            ))}
          </div>
          {highlights.length > 0 ? (
            <ul className="list-disc space-y-1.5 pl-5 text-sm text-muted">
              {highlights.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          ) : null}
        </CardBody>
      </Card>
    </div>
  )
}

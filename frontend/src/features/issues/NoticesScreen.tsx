import { Banner, PageHeader } from '@/ui'
import type { Notice } from '@/types/domain'
import { ago } from '../shared/format'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useApi } from '../shared/useApi'

const TONE = { CRITICAL: 'danger', WARNING: 'warning', INFO: 'info' } as const

export function NoticesScreen() {
  const notices = useApi<Notice[]>('/notices')
  return (
    <div>
      <PageHeader title="Campus Notices" description="Only notices that concern you, not a broadcast to everyone." />
      <QueryBoundary query={notices} isEmpty={(items) => items.length === 0} emptyTitle="No notices right now">
        {(items) => (
          <div className="space-y-3">
            {items.map((notice) => (
              <Banner key={notice.id} tone={TONE[notice.severity]} title={notice.title}>
                <p>{notice.body}</p>
                <p className="mt-1 text-xs opacity-80">{notice.audience} · {ago(notice.at)}</p>
              </Banner>
            ))}
          </div>
        )}
      </QueryBoundary>
    </div>
  )
}

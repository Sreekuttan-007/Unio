import { CalendarClock, ClipboardList, DoorOpen, Siren } from 'lucide-react'
import { Badge, Banner, Button, Card, CardHeader, ListRow, PageHeader, StatTile } from '@/ui'
import type { Notice, ReportSummary, TodaySession } from '@/types/domain'
import { useAuth } from '@/platform/auth/AuthProvider'
import { IncidentStatusBadge } from '../shared/badges'
import { ago } from '../shared/format'
import { QueryBoundary } from '../shared/QueryBoundary'
import { SessionCard } from '../shell/SessionCard'
import { useApi } from '../shared/useApi'
import { useNavTo } from '../shared/useNavTo'


function greeting(name: string) {
  const hour = new Date().getHours()
  return `${hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'}, ${name.split(' ')[0]}`
}

export function StudentHome() {
  const { bootstrap } = useAuth()
  const { go } = useNavTo()
  const reports = useApi<ReportSummary[]>('/issues/mine')
  const notices = useApi<Notice[]>('/notices')
  const open = (reports.data ?? []).filter((report) => !['RESOLVED', 'CLOSED'].includes(report.status))
  const critical = (notices.data ?? []).find((notice) => notice.severity === 'CRITICAL')

  return (
    <div className="space-y-6">
      <PageHeader title="Home" eyebrow={greeting(bootstrap?.user.name ?? '')} description="What you reported, and what is happening on campus." actions={<Button onClick={() => go('student.report')}>Report an issue</Button>} />
      {critical ? <Banner tone="danger" role="alert" title={critical.title} action={<Button variant="secondary" compact onClick={() => go('student.notices')}>Read</Button>}>{critical.body}</Banner> : null}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatTile label="Open reports" value={open.length} tone="accent" icon={<ClipboardList aria-hidden="true" className="size-5" />} hint="Still being handled" />
        <StatTile label="Joined an existing incident" value={(reports.data ?? []).filter((report) => report.incidentReportCount > 1).length} icon={<Siren aria-hidden="true" className="size-5" />} hint="Others reported the same thing" />
        <StatTile label="Notices for you" value={(notices.data ?? []).length} tone="warning" icon={<CalendarClock aria-hidden="true" className="size-5" />} hint="Only what concerns you" />
      </div>
      <Card>
        <CardHeader title="Your reports" action={<Button variant="ghost" compact onClick={() => go('student.myReports')}>See all</Button>} />
        <QueryBoundary query={reports} isEmpty={(items) => items.length === 0} emptyTitle="Nothing reported yet">
          {(items) => items.slice(0, 3).map((item) => <ListRow key={item.id} title={item.title} subtitle={`${item.incidentId} · ${ago(item.submittedAt)}`} trailing={<IncidentStatusBadge status={item.status} />} />)}
        </QueryBoundary>
      </Card>
      <SessionCard />
    </div>
  )
}

export function FacultyHome() {
  const { bootstrap } = useAuth()
  const { go } = useNavTo()
  const sessions = useApi<TodaySession[]>('/timetable/today')
  const affected = (sessions.data ?? []).filter((session) => session.status === 'AFFECTED')

  return (
    <div className="space-y-6">
      <PageHeader title="Home" eyebrow={greeting(bootstrap?.user.name ?? '')} description="Today's sessions, and anything disrupting them." actions={<Button onClick={() => go('faculty.booking')}>Book a room</Button>} />
      {affected.length > 0 ? (
        <Banner tone="danger" role="alert" title={`${affected.length} of your sessions today are affected`} action={<Button variant="secondary" compact onClick={() => go('faculty.impact')}>See alternatives</Button>}>
          A power fault on Aryabhata floor 2 has closed rooms ARB-201 to ARB-206.
        </Banner>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatTile label="Sessions today" value={(sessions.data ?? []).length} icon={<CalendarClock aria-hidden="true" className="size-5" />} />
        <StatTile label="Affected by disruption" value={affected.length} tone={affected.length ? 'danger' : 'success'} icon={<Siren aria-hidden="true" className="size-5" />} />
        <StatTile label="Rooms free for booking" value="41" icon={<DoorOpen aria-hidden="true" className="size-5" />} hint="Right now" />
      </div>
      <Card>
        <CardHeader title="Today" />
        <QueryBoundary query={sessions} isEmpty={(items) => items.length === 0} emptyTitle="No sessions today">
          {(items) => items.map((session) => (
            <ListRow
              key={session.id}
              title={session.course}
              subtitle={`${session.start} to ${session.end} · ${session.room} · ${session.group}`}
              trailing={session.status === 'AFFECTED' ? <Badge tone="danger">Affected</Badge> : <Badge tone="success">As planned</Badge>}
            />
          ))}
        </QueryBoundary>
      </Card>
      <SessionCard />
    </div>
  )
}

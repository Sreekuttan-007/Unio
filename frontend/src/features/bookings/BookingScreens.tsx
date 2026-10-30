import { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { Badge, Banner, Button, Card, CardBody, CardHeader, ImpactChain, ListRow, PageHeader, SelectField, TextField, type ImpactStep } from '@/ui'
import type { BookingCheck, BookingRow, ImpactReport, TodaySession } from '@/types/domain'
import { describeError } from '../shared/errors'
import { dateTime, inputDate, titleCase } from '../shared/format'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useAction, useApi } from '../shared/useApi'
import { useNavTo } from '../shared/useNavTo'

interface RoomOption {
  code: string
  type: string
  capacity: number
  building: string
  status: string
  closedReason: string | null
}

const KINDS = [
  { value: 'LECTURE', label: 'Lecture or tutorial' },
  { value: 'PRACTICAL', label: 'Practical' },
  { value: 'EXAM', label: 'Exam' },
  { value: 'EVENT', label: 'Event' },
]

const when = (date: string, time: string) => new Date(`${date}T${time}:00`).toISOString()
const timeOf = (iso: string) => {
  const date = new Date(iso)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

interface BookingBody {
  roomCode: string
  start: string
  end: string
  headcount: number
  kind: string
}

export function BookRoomScreen() {
  const rooms = useApi<RoomOption[]>('/campus/rooms', { query: { bookable: true } })
  const [form, setForm] = useState({ roomCode: 'ARB-204', date: inputDate(), start: '09:00', end: '10:30', headcount: 40, purpose: 'Revision class', kind: 'LECTURE' })
  const [result, setResult] = useState<BookingCheck | null>(null)
  const [confirmed, setConfirmed] = useState<BookingRow | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reason, setReason] = useState('')

  const check = useAction<BookingBody, BookingCheck>('POST', '/bookings/check')
  const book = useAction<BookingBody & { purpose: string; expectedStateToken?: string; acknowledgedCodes?: string[]; overrideReason?: string }, BookingRow>('POST', '/bookings', ['/bookings'], { idempotent: true })

  const payload = (next = form): BookingBody => ({ roomCode: next.roomCode, start: when(next.date, next.start), end: when(next.date, next.end), headcount: next.headcount, kind: next.kind })
  const edit = (change: Partial<typeof form>) => {
    setForm({ ...form, ...change })
    setResult(null)
  }

  const run = async (next = form) => {
    setError(null)
    setConfirmed(null)
    setReason('')
    setForm(next)
    try {
      setResult(await check.mutateAsync(payload(next)))
    } catch (failure) {
      setResult(null)
      setError(describeError(failure))
    }
  }

  const confirm = async () => {
    if (!result) return
    try {
      const warned = result.decision === 'WARN'
      setConfirmed(
        await book.mutateAsync({
          ...payload(),
          purpose: form.purpose,
          expectedStateToken: result.stateToken,
          acknowledgedCodes: warned ? result.findings.map((finding) => finding.code) : undefined,
          overrideReason: warned ? reason.trim() : undefined,
        }),
      )
      setResult(null)
    } catch (failure) {
      setError(describeError(failure))
    }
  }

  const warned = result?.decision === 'WARN'
  const blocked = result && result.decision !== 'ALLOW' && !warned

  return (
    <div className="space-y-6">
      <PageHeader title="Book a Room" description="Conflicts are checked on the server, so two people can never hold the same room." />
      {error ? <Banner tone="danger" title="That did not work" role="alert">{error}</Banner> : null}
      {confirmed ? <Banner tone="success" title={`Booked ${confirmed.roomCode}`} role="status">{dateTime(confirmed.start)} to {dateTime(confirmed.end)}. Confirmation {confirmed.id}.</Banner> : null}

      <Card>
        <CardHeader title="When and where" />
        <CardBody className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <QueryBoundary query={rooms}>
            {(options) => (
              <SelectField
                label="Room"
                value={form.roomCode}
                onChange={(event) => edit({ roomCode: event.target.value })}
                options={options.map((room) => ({ value: room.code, label: `${room.code} · ${titleCase(room.type)} · seats ${room.capacity}${room.status !== 'OPEN' ? ` · ${room.status.toLowerCase()}` : ''}` }))}
              />
            )}
          </QueryBoundary>
          <TextField label="Date" type="date" value={form.date} onChange={(event) => edit({ date: event.target.value })} />
          <TextField label="People" type="number" min={1} value={form.headcount} onChange={(event) => edit({ headcount: Number(event.target.value) })} />
          <TextField label="From" type="time" step={900} value={form.start} onChange={(event) => edit({ start: event.target.value })} />
          <TextField label="To" type="time" step={900} value={form.end} onChange={(event) => edit({ end: event.target.value })} />
          <SelectField label="What for" value={form.kind} onChange={(event) => edit({ kind: event.target.value })} options={KINDS} />
          <div className="sm:col-span-2">
            <TextField label="Purpose" value={form.purpose} onChange={(event) => edit({ purpose: event.target.value })} />
          </div>
          <div className="flex items-end">
            <Button loading={check.isPending} onClick={() => void run()}>Check availability</Button>
          </div>
        </CardBody>
      </Card>

      {result?.decision === 'ALLOW' ? (
        <Banner tone="success" title={`${form.roomCode} is free then`} role="status" action={<Button loading={book.isPending} disabled={!form.purpose.trim()} onClick={() => void confirm()}>Book it</Button>}>
          No clashes. The server checks again at the moment you book.
        </Banner>
      ) : null}

      {warned && result ? (
        <Banner tone="warning" title="You can book this, with a reason" role="status" data-testid="warning-panel">
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {result.findings.map((finding) => <li key={finding.code}>{finding.message}</li>)}
          </ul>
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <div className="min-w-56 flex-1">
              <TextField label="Why is this fine?" value={reason} onChange={(event) => setReason(event.target.value)} hint="Kept in the audit trail" />
            </div>
            <Button loading={book.isPending} disabled={reason.trim().length < 5 || !form.purpose.trim()} onClick={() => void confirm()}>Book anyway</Button>
          </div>
        </Banner>
      ) : null}

      {blocked && result ? (
        <div className="space-y-4" data-testid="conflict-panel">
          <Banner tone="danger" title={`${form.roomCode} cannot be booked then`} role="alert">
            <ul className="mt-1 list-disc space-y-1 pl-5">
              {result.findings.map((finding) => <li key={`${finding.code}-${finding.message}`}>{finding.message}</li>)}
            </ul>
          </Banner>
          {result.affectedClasses.length > 0 ? (
            <Card>
              <CardHeader title="In the way" description="These hold the room at that time." />
              {result.affectedClasses.map((item) => <ListRow key={`${item.course}-${item.start}`} title={item.course} subtitle={`${item.group} · ${item.headcount} people`} meta={`${item.start} to ${item.end}`} />)}
            </Card>
          ) : null}
          {result.alternatives.length > 0 ? (
            <Card>
              <CardHeader title="Rooms that would work" description="Free at that time and big enough." />
              {result.alternatives.map((room) => (
                <ListRow
                  key={room.roomCode}
                  testId={`alt-${room.roomCode}`}
                  title={`${room.roomCode} · ${titleCase(room.type)} · seats ${room.capacity}`}
                  subtitle={`${room.building} · ${room.fit}`}
                  trailing={<Button variant="secondary" compact onClick={() => void run({ ...form, roomCode: room.roomCode })}>Use this room</Button>}
                />
              ))}
            </Card>
          ) : null}
          {result.timeAlternatives && result.timeAlternatives.length > 0 ? (
            <Card>
              <CardHeader title={`Other times in ${form.roomCode}`} description="Same room, same length." />
              {result.timeAlternatives.map((slot) => (
                <ListRow
                  key={slot.start}
                  testId={`time-${timeOf(slot.start)}`}
                  title={slot.label}
                  subtitle={slot.reason}
                  trailing={<Button variant="secondary" compact onClick={() => void run({ ...form, start: timeOf(slot.start), end: timeOf(slot.end) })}>Use this time</Button>}
                />
              ))}
            </Card>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

export function MyBookingsScreen({ title = 'My Bookings', description = 'Upcoming, past and rescheduled.' }: { title?: string; description?: string }) {
  const bookings = useApi<{ items: BookingRow[] }>('/bookings')
  const [error, setError] = useState<string | null>(null)
  const cancel = useAction<{ id: string }>('POST', (body) => `/bookings/${body.id}/cancel`, ['/bookings'])
  const TONE = { CONFIRMED: 'success', REQUESTED: 'info', RESCHEDULED: 'warning', CANCELLED: 'neutral', REJECTED: 'danger' } as const

  const onCancel = async (id: string) => {
    setError(null)
    try {
      await cancel.mutateAsync({ id })
    } catch (failure) {
      setError(describeError(failure))
    }
  }

  return (
    <div>
      <PageHeader title={title} description={description} />
      {error ? <Banner tone="danger" title="That did not work" role="alert">{error}</Banner> : null}
      <QueryBoundary query={bookings} isEmpty={(data) => data.items.length === 0} emptyTitle="No bookings yet">
        {(data) => (
          <Card>
            {data.items.map((booking) => {
              const canCancel = booking.availableActions?.some((action) => action.key === 'booking.cancel')
              const why = booking.unavailableActions?.find((action) => action.key === 'booking.cancel')?.reason
              return (
                <ListRow
                  key={booking.id}
                  title={`${booking.roomCode} · ${booking.purpose}`}
                  subtitle={`${dateTime(booking.start)} to ${dateTime(booking.end)} · ${booking.building} · ${booking.requester}${why && booking.status !== 'CANCELLED' ? ` · ${why}` : ''}`}
                  trailing={
                    <span className="flex items-center gap-2">
                      <Badge tone={TONE[booking.status]}>{titleCase(booking.status)}</Badge>
                      {canCancel ? <Button variant="ghost" compact onClick={() => void onCancel(booking.id)}>Cancel</Button> : null}
                    </span>
                  }
                />
              )
            })}
          </Card>
        )}
      </QueryBoundary>
    </div>
  )
}

export function AcademicImpactScreen() {
  const sessions = useApi<TodaySession[]>('/timetable/today')
  // The incidents behind this person's affected classes, from the faculty-scoped impact view.
  const academic = useApi<{ incidentId: string; title: string }[]>('/cascading/academic')
  const source = academic.data?.[0]?.incidentId
  const impact = useApi<ImpactReport>(`/cascading/impact/${source ?? 'none'}`, { enabled: !!source })
  const { go } = useNavTo()
  const affected = (sessions.data ?? []).filter((session) => session.status === 'AFFECTED')

  return (
    <div className="space-y-6">
      <PageHeader title="Academic Impact" description="Which of your sessions a live incident affects, and where you can go instead." />
      <QueryBoundary query={sessions} isEmpty={() => affected.length === 0} emptyTitle="None of your sessions are affected" emptyDescription="You will see them here the moment an incident touches one of your rooms.">
        {() => (
          <div className="space-y-4">
            {affected.map((session) => (
              <Card key={session.id} data-testid={`affected-${session.id}`}>
                <CardBody className="space-y-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="text-base font-semibold text-ink">{session.course}</p>
                      <p className="text-sm text-muted">{session.start} to {session.end} · {session.room} · {session.group} · {session.headcount} students</p>
                    </div>
                    <Badge tone="danger">{titleCase(session.kind)} affected</Badge>
                  </div>
                  {session.note ? <p className="text-sm text-ink">{session.note}</p> : null}
                  {session.alternative ? (
                    <div className="flex flex-wrap items-center gap-3 rounded-md bg-success-soft px-3 py-2 text-sm text-success-ink">
                      <ArrowRight aria-hidden="true" className="size-4" />
                      <span className="flex-1">Suggested: <strong>{session.alternative.roomCode}</strong>. {session.alternative.note}.</span>
                      <Button variant="secondary" compact onClick={() => go('faculty.booking')}>Book it</Button>
                    </div>
                  ) : null}
                </CardBody>
              </Card>
            ))}
          </div>
        )}
      </QueryBoundary>
      {source ? <QueryBoundary query={impact}>
        {(data) => (
          <Card>
            <CardHeader title="Why these sessions are affected" description="Traced through stored relationships between the fault, rooms and timetable." />
            <CardBody>
              <ImpactChain steps={data.chain as ImpactStep[]} />
            </CardBody>
          </Card>
        )}
      </QueryBoundary> : null}
    </div>
  )
}

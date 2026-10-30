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

const when = (date: string, time: string) => new Date(`${date}T${time}:00`).toISOString()

export function BookRoomScreen() {
  const rooms = useApi<RoomOption[]>('/campus/rooms', { query: { bookable: true } })
  const [form, setForm] = useState({ roomCode: 'ARB-204', date: inputDate(), start: '09:00', end: '10:30', headcount: 40, purpose: 'Revision class' })
  const [result, setResult] = useState<BookingCheck | null>(null)
  const [confirmed, setConfirmed] = useState<BookingRow | null>(null)
  const [error, setError] = useState<string | null>(null)

  const check = useAction<{ roomCode: string; start: string; end: string; headcount: number }, BookingCheck>('POST', '/bookings/check')
  const book = useAction<{ roomCode: string; start: string; end: string; headcount: number; purpose: string }, BookingRow>('POST', '/bookings', ['/bookings'], { idempotent: true })

  const payload = { roomCode: form.roomCode, start: when(form.date, form.start), end: when(form.date, form.end), headcount: form.headcount }

  const run = async (override?: string) => {
    setError(null)
    setConfirmed(null)
    const next = override ? { ...form, roomCode: override } : form
    if (override) setForm(next)
    try {
      setResult(await check.mutateAsync({ ...payload, roomCode: next.roomCode }))
    } catch (failure) {
      setError(describeError(failure))
    }
  }

  const confirm = async () => {
    try {
      setConfirmed(await book.mutateAsync({ ...payload, purpose: form.purpose }))
      setResult(null)
    } catch (failure) {
      setError(describeError(failure))
    }
  }

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
                onChange={(event) => setForm({ ...form, roomCode: event.target.value })}
                options={options.map((room) => ({ value: room.code, label: `${room.code} · ${titleCase(room.type)} · seats ${room.capacity}${room.status === 'CLOSED' ? ' · closed' : ''}` }))}
              />
            )}
          </QueryBoundary>
          <TextField label="Date" type="date" value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} />
          <TextField label="People" type="number" min={1} value={form.headcount} onChange={(event) => setForm({ ...form, headcount: Number(event.target.value) })} />
          <TextField label="From" type="time" value={form.start} onChange={(event) => setForm({ ...form, start: event.target.value })} />
          <TextField label="To" type="time" value={form.end} onChange={(event) => setForm({ ...form, end: event.target.value })} />
          <TextField label="Purpose" value={form.purpose} onChange={(event) => setForm({ ...form, purpose: event.target.value })} />
          <div className="sm:col-span-2 lg:col-span-3">
            <Button loading={check.isPending} onClick={() => void run()}>Check availability</Button>
          </div>
        </CardBody>
      </Card>

      {result?.allowed ? (
        <Banner tone="success" title={`${form.roomCode} is free then`} role="status" action={<Button loading={book.isPending} onClick={() => void confirm()}>Book it</Button>}>
          No clashes. The server checks again at the moment you book.
        </Banner>
      ) : null}

      {result && !result.allowed ? (
        <div className="space-y-4" data-testid="conflict-panel">
          <Banner tone="danger" title={`${form.roomCode} cannot be booked then`} role="alert">
            <ul className="mt-1 list-disc space-y-1 pl-5">
              {result.findings.map((finding) => <li key={finding.code}>{finding.message}</li>)}
            </ul>
          </Banner>
          {result.affectedClasses.length > 0 ? (
            <Card>
              <CardHeader title="Classes in the way" description="These are the sessions that hold the room." />
              {result.affectedClasses.map((item) => <ListRow key={item.course} title={item.course} subtitle={`${item.group} · ${item.headcount} students`} meta={`${item.start} to ${item.end}`} />)}
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
                  trailing={<Button variant="secondary" compact onClick={() => void run(room.roomCode)}>Use this room</Button>}
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
  const cancel = useAction<{ id: string }>('POST', (body) => `/bookings/${body.id}/cancel`, ['/bookings'])
  const TONE = { CONFIRMED: 'success', REQUESTED: 'info', RESCHEDULED: 'warning', CANCELLED: 'neutral', REJECTED: 'danger' } as const
  return (
    <div>
      <PageHeader title={title} description={description} />
      <QueryBoundary query={bookings} isEmpty={(data) => data.items.length === 0} emptyTitle="No bookings yet">
        {(data) => (
          <Card>
            {data.items.map((booking) => (
              <ListRow
                key={booking.id}
                title={`${booking.roomCode} · ${booking.purpose}`}
                subtitle={`${dateTime(booking.start)} to ${dateTime(booking.end)} · ${booking.building} · ${booking.requester}`}
                trailing={
                  <span className="flex items-center gap-2">
                    <Badge tone={TONE[booking.status]}>{titleCase(booking.status)}</Badge>
                    {['CONFIRMED', 'REQUESTED'].includes(booking.status) ? <Button variant="ghost" compact onClick={() => cancel.mutate({ id: booking.id })}>Cancel</Button> : null}
                  </span>
                }
              />
            ))}
          </Card>
        )}
      </QueryBoundary>
    </div>
  )
}

export function AcademicImpactScreen() {
  const sessions = useApi<TodaySession[]>('/timetable/today')
  const impact = useApi<ImpactReport>('/cascading/impact/INC-1041')
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
      <QueryBoundary query={impact}>
        {(data) => (
          <Card>
            <CardHeader title="Why these sessions are affected" description="Traced through stored relationships between the fault, rooms and timetable." />
            <CardBody>
              <ImpactChain steps={data.chain as ImpactStep[]} />
            </CardBody>
          </Card>
        )}
      </QueryBoundary>
    </div>
  )
}

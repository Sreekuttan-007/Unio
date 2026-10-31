import { useEffect, useState } from 'react'
import {
  Badge,
  BottomNav,
  Button,
  Card,
  CardBody,
  CardHeader,
  Checkbox,
  DataTable,
  EmptyState,
  ErrorState,
  GlassButton,
  LoginCard,
  NotPermitted,
  OfflineState,
  PageHeader,
  PlannedScreen,
  ScreenSkeleton,
  SelectField,
  SideNav,
  TextField,
  WakingBanner,
  type NavEntryView,
  type ThemePreference,
} from '@/ui'

/**
 * Every ui/ component with hand-written props, in every state, with no backend and no sign-in.
 * Open /dev/ui in development to restyle the product safely: if a component cannot be shown here
 * from plain props, it does not belong in ui/. Not mounted in production builds.
 */

const ACCENTS = ['sky', 'indigo', 'teal', 'rose', 'violet', 'amber', 'slate'] as const
const THEMES: ThemePreference[] = ['light', 'dark', 'system']

const NAV: NavEntryView[] = [
  { key: 'a', label: 'Command Centre', path: '/dev/ui#a', icon: 'radar' },
  { key: 'b', label: 'Live Campus Map', path: '/dev/ui#b', icon: 'map' },
  { key: 'c', label: 'Incident Triage', path: '/dev/ui#c', icon: 'siren', badge: 4 },
  { key: 'd', label: 'Work Orders', path: '/dev/ui#d', icon: 'wrench' },
  { key: 'e', label: 'Technicians', path: '/dev/ui#e', icon: 'hard-hat' },
  { key: 'f', label: 'Inventory', path: '/dev/ui#f', icon: 'package' },
]

const ROWS = [
  { id: '1', name: 'Wi-Fi outage in Block A', status: 'In progress' },
  { id: '2', name: 'Projector not working in A204', status: 'Acknowledged' },
]

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">{title}</h2>
      {children}
    </section>
  )
}

export function UiGallery() {
  const [accent, setAccent] = useState<(typeof ACCENTS)[number]>('sky')
  const [theme, setTheme] = useState<ThemePreference>('system')

  useEffect(() => {
    const root = document.documentElement
    root.setAttribute('data-accent', accent)
    if (theme === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
  }, [accent, theme])

  return (
    <div className="mx-auto max-w-5xl space-y-10 px-4 py-8">
      <PageHeader title="UI gallery" description="Every component, every state, no backend. Change tokens.css and watch everything here." />

      <Card>
        <CardBody className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-ink">Role accent</span>
            {ACCENTS.map((name) => (
              <button
                key={name}
                type="button"
                data-accent={name}
                aria-pressed={accent === name}
                onClick={() => setAccent(name)}
                className="flex min-h-11 items-center gap-2 rounded-full border border-line-strong px-3 text-sm aria-pressed:bg-accent-soft aria-pressed:text-accent-ink"
              >
                <span aria-hidden="true" className="size-3 rounded-full bg-accent" />
                {name}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-ink">Theme</span>
            {THEMES.map((name) => (
              <Button key={name} compact variant={theme === name ? 'primary' : 'secondary'} onClick={() => setTheme(name)}>
                {name}
              </Button>
            ))}
          </div>
        </CardBody>
      </Card>

      <Section title="Buttons & Glassmorphism">
        <div className="flex flex-wrap items-center gap-4">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="glass">Glass</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
          <Button loading>Saving</Button>
          <Button disabled>Disabled</Button>
          <Button compact>Compact</Button>
        </div>
        <div className="pt-2">
          <GlassButton>Generate</GlassButton>
        </div>
      </Section>

      <Section title="Badges (text always accompanies colour)">
        <div className="flex flex-wrap gap-2">
          <Badge>Neutral</Badge>
          <Badge tone="accent">Accent</Badge>
          <Badge tone="success">Resolved</Badge>
          <Badge tone="warning">At risk</Badge>
          <Badge tone="danger">Breached</Badge>
          <Badge tone="info">Acknowledged</Badge>
        </div>
      </Section>

      <Section title="Cards and tables">
        <Card>
          <CardHeader title="Open incidents" description="Newest first" action={<Button compact variant="secondary">Filter</Button>} />
          <DataTable
            caption="Incidents"
            rows={ROWS}
            rowKey={(row) => row.id}
            columns={[
              { key: 'name', header: 'Incident', cell: (row) => row.name },
              { key: 'status', header: 'Status', cell: (row) => <Badge tone="info">{row.status}</Badge> },
            ]}
          />
        </Card>
      </Section>

      <Section title="Form fields">
        <Card>
          <CardBody className="grid gap-4 sm:grid-cols-2">
            <TextField label="Room" placeholder="A204" hint="Building letter then room number." />
            <TextField label="Email" defaultValue="not-an-email" error="Enter a valid email address." />
            <SelectField label="Priority" options={[{ value: 'p1', label: 'P1 critical' }, { value: 'p2', label: 'P2 high' }]} />
            <div>
              <Checkbox label="Notify affected faculty" description="Only people with a session in the affected rooms." defaultChecked />
              <Checkbox label="Post to the status page" />
            </div>
          </CardBody>
        </Card>
      </Section>

      <Section title="Screen states">
        <div className="grid gap-4 md:grid-cols-2">
          <ScreenSkeleton />
          <EmptyState title="Nothing here yet" description="New reports will appear as they arrive." action={<Button variant="secondary">Report an issue</Button>} />
          <ErrorState description="The server answered 500." onRetry={() => undefined} />
          <NotPermitted onHome={() => undefined} />
          <OfflineState onRetry={() => undefined} />
          <WakingBanner />
        </div>
      </Section>

      <Section title="Navigation (desktop sidebar is fixed, so it is shown in a frame)">
        <div className="relative h-96 overflow-hidden rounded-lg border border-line [transform:translateZ(0)]">
          <SideNav items={NAV} activePath="/dev/ui#c" roleLabel="Facilities Administrator" onNavigate={() => undefined} />
        </div>
        <div className="relative h-40 overflow-hidden rounded-lg border border-line [transform:translateZ(0)]">
          <BottomNav items={NAV} activePath="/dev/ui#a" onNavigate={() => undefined} />
        </div>
      </Section>

      <Section title="Planned screen">
        <PlannedScreen
          title="Collision Review"
          summary="Every conflict the engine found, why, and any override with its reason."
          phase={5}
          requirements={['M4', 'M5', 'M7']}
          highlights={['Hard conflicts block and cannot be overridden', 'Soft conflicts need a reason, which is audited']}
        />
      </Section>

      <Section title="Login">
        <div className="overflow-hidden rounded-lg border border-line">
          <LoginCard
            demoAccounts={[
              { email: 'student@unio.demo', name: 'Asha Nair', roleLabel: 'Student', accent: 'sky' },
              { email: 'tech@unio.demo', name: 'Ravi Kumar', roleLabel: 'Technician', accent: 'amber' },
              { email: 'procure@unio.demo', name: 'Divya Pillai', roleLabel: 'Procurement Approver', accent: 'violet' },
              { email: 'facilities@unio.demo', name: 'Arjun Menon', roleLabel: 'Facilities Administrator', accent: 'rose' },
            ]}
            busyEmail={null}
            submitting={false}
            error="Incorrect email or password."
            waking
            onDemoLogin={() => undefined}
            onSubmit={() => undefined}
          />
        </div>
      </Section>
    </div>
  )
}

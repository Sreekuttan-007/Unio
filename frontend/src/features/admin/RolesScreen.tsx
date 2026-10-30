import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Info } from 'lucide-react'
import { useMemo, useState } from 'react'
import { api } from '@/platform/api/client'
import type { RoleDto } from '@/platform/api/types'
import { Badge, Button, Card, CardBody, CardHeader, Checkbox, ErrorState, PageHeader, ScreenSkeleton, cn } from '@/ui'
import { describeError } from '../shared/errors'

const GROUPS: Record<string, string> = {
  issue: 'Issues',
  incident: 'Incidents',
  inbox: 'Intake inbox',
  booking: 'Room bookings',
  workorder: 'Work orders',
  technician: 'Technicians',
  collision: 'Collision engine',
  cascade: 'Cascading impact',
  simulation: 'What-if simulator',
  inventory: 'Inventory',
  approval: 'Approvals',
  purchase: 'Purchase orders',
  invoice: 'Invoices',
  receipt: 'Goods receipts',
  sla: 'SLA',
  map: 'Campus map',
  analytics: 'Analytics',
  audit: 'Audit',
  admin: 'Administration',
}

const groupOf = (permission: string) => permission.split('.')[0] ?? permission

export function RolesScreen() {
  const queryClient = useQueryClient()
  const roles = useQuery({ queryKey: ['admin-roles'], queryFn: () => api<RoleDto[]>('/admin/roles') })
  const catalogue = useQuery({ queryKey: ['admin-permissions'], queryFn: () => api<string[]>('/admin/permissions') })
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [draft, setDraft] = useState<Set<string> | null>(null)
  const [message, setMessage] = useState<{ tone: 'error' | 'ok'; text: string } | null>(null)

  const selected = roles.data?.find((role) => role.key === (selectedKey ?? roles.data[0]?.key))
  const working = draft ?? new Set(selected?.permissions ?? [])
  const dirty = selected ? working.size !== selected.permissions.length || selected.permissions.some((p) => !working.has(p)) : false

  const grouped = useMemo(() => {
    const byGroup = new Map<string, string[]>()
    for (const permission of catalogue.data ?? []) {
      byGroup.set(groupOf(permission), [...(byGroup.get(groupOf(permission)) ?? []), permission])
    }
    return [...byGroup.entries()]
  }, [catalogue.data])

  const save = useMutation({
    mutationFn: (job: { key: string; permissions: string[] }) =>
      api<RoleDto>(`/admin/roles/${job.key}`, { method: 'PUT', body: { permissions: job.permissions } }),
    onSuccess: async (role) => {
      setMessage({ tone: 'ok', text: `${role.label} updated. Their sidebar changes on the next page load.` })
      setDraft(null)
      await queryClient.invalidateQueries({ queryKey: ['admin-roles'] })
    },
    onError: (error) => setMessage({ tone: 'error', text: describeError(error) }),
  })

  const choose = (key: string) => {
    setSelectedKey(key)
    setDraft(null)
    setMessage(null)
  }

  const toggle = (permission: string, on: boolean) => {
    const next = new Set(working)
    if (on) next.add(permission)
    else next.delete(permission)
    setDraft(next)
  }

  if (roles.isPending || catalogue.isPending) return <ScreenSkeleton />
  if (roles.isError || catalogue.isError || !selected) {
    return <ErrorState description={describeError(roles.error ?? catalogue.error)} onRetry={() => void roles.refetch()} />
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Roles & Permissions" description="Edit what each role can do. The server checks every request against this, and the sidebar follows it." />

      <p className="flex items-start gap-2 rounded-md bg-info-soft px-4 py-3 text-sm text-info-ink">
        <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        Configuration is not business authority. The server refuses to give System Administrators approval, assignment or stock powers.
      </p>

      {message ? (
        <p
          role={message.tone === 'error' ? 'alert' : 'status'}
          data-testid="roles-message"
          className={cn('rounded-md px-4 py-3 text-sm', message.tone === 'error' ? 'bg-danger-soft text-danger-ink' : 'bg-success-soft text-success-ink')}
        >
          {message.text}
        </p>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
        <Card>
          <CardBody className="space-y-1 p-2">
            {roles.data.map((role) => (
              <button
                key={role.key}
                type="button"
                data-accent={role.accent}
                aria-pressed={role.key === selected.key}
                onClick={() => choose(role.key)}
                className={cn(
                  'flex min-h-11 w-full items-center gap-3 rounded-md px-3 text-left text-sm font-medium',
                  role.key === selected.key ? 'bg-accent-soft text-accent-ink' : 'text-ink hover:bg-surface-2',
                )}
              >
                <span aria-hidden="true" className="size-3 rounded-full bg-accent" />
                <span className="flex-1">{role.label}</span>
                <span className="text-xs text-muted">{role.permissions.length}</span>
              </button>
            ))}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title={selected.label}
            description={`${working.size} of ${catalogue.data.length} permissions`}
            action={
              <Button loading={save.isPending} disabled={!dirty} onClick={() => save.mutate({ key: selected.key, permissions: [...working] })}>
                Save changes
              </Button>
            }
          />
          <CardBody className="space-y-5">
            {grouped.map(([group, permissions]) => (
              <fieldset key={group}>
                <legend className="mb-1 flex items-center gap-2 text-sm font-semibold text-ink">
                  {GROUPS[group] ?? group}
                  <Badge tone="neutral">{permissions.filter((p) => working.has(p)).length}/{permissions.length}</Badge>
                </legend>
                <div className="grid gap-x-4 sm:grid-cols-2">
                  {permissions.map((permission) => (
                    <Checkbox key={permission} label={permission} checked={working.has(permission)} onChange={(event) => toggle(permission, event.target.checked)} />
                  ))}
                </div>
              </fieldset>
            ))}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { api, newId } from '@/platform/api/client'
import type { CreateUserBody, RoleDto, UserDto, UserPage } from '@/platform/api/types'
import { Badge, Button, Card, CardBody, CardHeader, DataTable, ErrorState, PageHeader, ScreenSkeleton, SelectField, TextField, type Column } from '@/ui'
import { describeError } from '../shared/errors'

const EMPTY_FORM = { name: '', email: '', password: '', roleKey: '' }

export function UsersScreen() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(0)
  const [message, setMessage] = useState<string | null>(null)
  const [form, setForm] = useState(EMPTY_FORM)
  // One key per form fill: a double tap or a retry creates one user, not two.
  const [createKey, setCreateKey] = useState(newId)

  const users = useQuery({ queryKey: ['admin-users', page], queryFn: () => api<UserPage>('/admin/users', { query: { page, size: 20 } }) })
  const roles = useQuery({ queryKey: ['admin-roles'], queryFn: () => api<RoleDto[]>('/admin/roles') })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['admin-users'] })

  const change = useMutation({
    mutationFn: (job: { path: string; body: unknown }) => api<UserDto>(job.path, { method: 'PATCH', body: job.body }),
    onSuccess: () => {
      setMessage(null)
      return refresh()
    },
    onError: (error) => setMessage(describeError(error)),
  })

  const create = useMutation({
    mutationFn: (body: CreateUserBody) => api<UserDto>('/admin/users', { method: 'POST', body, idempotencyKey: createKey }),
    onSuccess: () => {
      setMessage(null)
      setForm(EMPTY_FORM)
      setCreateKey(newId())
      return refresh()
    },
    onError: (error) => setMessage(describeError(error)),
  })

  const roleOptions = (roles.data ?? []).map((role) => ({ value: role.key, label: role.label }))

  const columns: Column<UserDto>[] = [
    {
      key: 'name',
      header: 'Person',
      cell: (user) => (
        <div>
          <p className="font-medium">{user.name}</p>
          <p className="text-xs text-muted">{user.email}</p>
        </div>
      ),
    },
    { key: 'role', header: 'Role', cell: (user) => <Badge tone="accent">{roleOptions.find((o) => o.value === user.roleKey)?.label ?? user.roleKey}</Badge> },
    {
      key: 'status',
      header: 'Status',
      cell: (user) => <Badge tone={user.status === 'ACTIVE' ? 'success' : 'neutral'}>{user.status === 'ACTIVE' ? 'Active' : 'Inactive'}</Badge>,
    },
    {
      key: 'actions',
      header: 'Actions',
      cell: (user) => (
        <div className="flex flex-wrap items-center gap-2">
          {/* Only what the server says is possible right now. This screen never decides that itself. */}
          {user.availableActions.map((action) =>
            action.key === 'user.changeRole' ? (
              <select
                key={action.key}
                aria-label={`Change role for ${user.name}`}
                value={user.roleKey}
                disabled={change.isPending}
                onChange={(event) => change.mutate({ path: `/admin/users/${user.id}/role`, body: { roleKey: event.target.value } })}
                className="min-h-11 rounded-md border border-line-strong bg-surface px-2 text-sm"
              >
                {roleOptions.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            ) : (
              <Button
                key={action.key}
                compact
                variant={action.key === 'user.deactivate' ? 'danger' : 'secondary'}
                loading={change.isPending}
                onClick={() =>
                  change.mutate({ path: `/admin/users/${user.id}/status`, body: { status: action.key === 'user.deactivate' ? 'INACTIVE' : 'ACTIVE' } })
                }
              >
                {action.label}
              </Button>
            ),
          )}
          {user.unavailableActions.map((action) => (
            <span key={action.key} className="max-w-56 text-xs text-faint">{action.reason}</span>
          ))}
        </div>
      ),
    },
  ]

  const submit = (event: FormEvent) => {
    event.preventDefault()
    create.mutate(form)
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Users" description="Create accounts and manage who can sign in. Roles decide what each person sees." />

      {message ? (
        <p role="alert" data-testid="users-error" className="rounded-md bg-danger-soft px-4 py-3 text-sm text-danger-ink">{message}</p>
      ) : null}

      <Card>
        <CardHeader title="Add a user" description="They sign in with the email and password you set here." />
        <CardBody>
          <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2" noValidate>
            <TextField label="Full name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            <TextField label="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
            <TextField label="Password" type="password" hint="At least 10 characters." value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
            <SelectField
              label="Role"
              value={form.roleKey}
              onChange={(e) => setForm({ ...form, roleKey: e.target.value })}
              options={[{ value: '', label: 'Choose a role' }, ...roleOptions]}
            />
            <div className="sm:col-span-2">
              <Button type="submit" loading={create.isPending} disabled={!form.name || !form.email || form.password.length < 10 || !form.roleKey}>
                Create user
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>

      {users.isPending ? <ScreenSkeleton /> : null}
      {users.isError ? <ErrorState description={describeError(users.error)} onRetry={() => void users.refetch()} /> : null}
      {users.data ? (
        <Card>
          <DataTable columns={columns} rows={users.data.items} rowKey={(user) => user.id} caption="Users" />
          <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm text-muted">
            <span>{users.data.total} users</span>
            <span className="flex gap-2">
              <Button variant="secondary" compact disabled={page === 0} onClick={() => setPage((value) => value - 1)}>Previous</Button>
              <Button variant="secondary" compact disabled={(page + 1) * 20 >= users.data.total} onClick={() => setPage((value) => value + 1)}>Next</Button>
            </span>
          </div>
        </Card>
      ) : null}
    </div>
  )
}

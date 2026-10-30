import { useAuth } from '@/platform/auth/AuthProvider'
import { Badge, Card, CardBody, CardHeader } from '@/ui'

/** Shows what the server decided about this session. It is the on-screen proof of server-driven access. */
export function SessionCard() {
  const { bootstrap } = useAuth()
  if (!bootstrap) return null
  const scopes = Object.entries(bootstrap.scopes)
  return (
    <Card className="mb-6" data-testid="session-card">
      <CardHeader
        title="What the server decided for you"
        description="Your sidebar, screens and data rows come from this, not from the browser."
      />
      <CardBody className="grid gap-4 text-sm sm:grid-cols-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Signed in as</p>
          <p className="mt-1 font-medium text-ink">{bootstrap.user.name}</p>
          <p className="text-muted">{bootstrap.role.label}</p>
          {bootstrap.department ? <p className="text-muted">{bootstrap.department.name}</p> : null}
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Access</p>
          <p className="mt-1 text-ink">{bootstrap.permissions.length} permissions</p>
          <p className="text-muted">{bootstrap.navigation.length} screens in your sidebar</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Data scope</p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {scopes.length === 0 ? <span className="text-muted">None</span> : null}
            {scopes.map(([entity, scope]) => (
              <Badge key={entity} tone="accent">{entity.replace('_', ' ').toLowerCase()}: {scope.toLowerCase()}</Badge>
            ))}
          </div>
        </div>
      </CardBody>
    </Card>
  )
}

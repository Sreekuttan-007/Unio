import { lazy, type ComponentType, type LazyExoticComponent } from 'react'

/**
 * The only place a screen is declared. A route exists only when the server names its key in the
 * role navigation, so a screen for another role is never mounted and its code is never fetched.
 *
 * Each workspace is its own chunk: a Technician never downloads the procurement screens.
 * Keep this in step with backend app/users/navigation.py (a test in both projects enforces it).
 */
type Screens = Record<string, ComponentType>

const loaders = {
  student: () => import('@/features/workspaces/student'),
  faculty: () => import('@/features/workspaces/faculty'),
  department: () => import('@/features/workspaces/department'),
  facilities: () => import('@/features/workspaces/facilities'),
  procurement: () => import('@/features/workspaces/procurement'),
  technician: () => import('@/features/workspaces/technician'),
  system: () => import('@/features/workspaces/system'),
} satisfies Record<string, () => Promise<{ screens: Screens }>>

type Workspace = keyof typeof loaders

function screen(workspace: Workspace, key: string): LazyExoticComponent<ComponentType> {
  return lazy(async () => {
    const { screens } = await loaders[workspace]()
    const component = screens[key]
    if (!component) throw new Error(`Workspace ${workspace} has no screen for ${key}`)
    return { default: component }
  })
}

export const SCREEN_REGISTRY: Record<string, LazyExoticComponent<ComponentType>> = {
  'student.home': screen('student', 'student.home'),
  'student.report': screen('student', 'student.report'),
  'student.myReports': screen('student', 'student.myReports'),
  'student.notices': screen('student', 'student.notices'),
  'student.map': screen('student', 'student.map'),

  'faculty.home': screen('faculty', 'faculty.home'),
  'faculty.report': screen('faculty', 'faculty.report'),
  'faculty.booking': screen('faculty', 'faculty.booking'),
  'faculty.myBookings': screen('faculty', 'faculty.myBookings'),
  'faculty.impact': screen('faculty', 'faculty.impact'),
  'faculty.map': screen('faculty', 'faculty.map'),

  'dept.overview': screen('department', 'dept.overview'),
  'dept.incidents': screen('department', 'dept.incidents'),
  'dept.workRequests': screen('department', 'dept.workRequests'),
  'dept.resources': screen('department', 'dept.resources'),
  'dept.bookings': screen('department', 'dept.bookings'),
  'dept.inventory': screen('department', 'dept.inventory'),
  'dept.approvals': screen('department', 'dept.approvals'),
  'dept.sla': screen('department', 'dept.sla'),
  'dept.analytics': screen('department', 'dept.analytics'),

  'fac.command': screen('facilities', 'fac.command'),
  'fac.map': screen('facilities', 'fac.map'),
  'fac.inbox': screen('facilities', 'fac.inbox'),
  'fac.triage': screen('facilities', 'fac.triage'),
  'fac.workOrders': screen('facilities', 'fac.workOrders'),
  'fac.technicians': screen('facilities', 'fac.technicians'),
  'fac.collision': screen('facilities', 'fac.collision'),
  'fac.simulator': screen('facilities', 'fac.simulator'),
  'fac.inventory': screen('facilities', 'fac.inventory'),
  'fac.approvals': screen('facilities', 'fac.approvals'),
  'fac.sla': screen('facilities', 'fac.sla'),
  'fac.analytics': screen('facilities', 'fac.analytics'),
  'fac.audit': screen('facilities', 'fac.audit'),

  'proc.overview': screen('procurement', 'proc.overview'),
  'proc.queue': screen('procurement', 'proc.queue'),
  'proc.requests': screen('procurement', 'proc.requests'),
  'proc.orders': screen('procurement', 'proc.orders'),
  'proc.invoices': screen('procurement', 'proc.invoices'),
  'proc.discrepancies': screen('procurement', 'proc.discrepancies'),
  'proc.receipts': screen('procurement', 'proc.receipts'),
  'proc.history': screen('procurement', 'proc.history'),

  'tech.tasks': screen('technician', 'tech.tasks'),
  'tech.parts': screen('technician', 'tech.parts'),
  'tech.availability': screen('technician', 'tech.availability'),
  'tech.history': screen('technician', 'tech.history'),
  'tech.map': screen('technician', 'tech.map'),

  'sys.overview': screen('system', 'sys.overview'),
  'sys.users': screen('system', 'sys.users'),
  'sys.roles': screen('system', 'sys.roles'),
  'sys.campus': screen('system', 'sys.campus'),
  'sys.staff': screen('system', 'sys.staff'),
  'sys.inventoryMaster': screen('system', 'sys.inventoryMaster'),
  'sys.rules': screen('system', 'sys.rules'),
  'sys.slaPolicy': screen('system', 'sys.slaPolicy'),
  'sys.integrations': screen('system', 'sys.integrations'),
  'sys.audit': screen('system', 'sys.audit'),
  'sys.seed': screen('system', 'sys.seed'),
}

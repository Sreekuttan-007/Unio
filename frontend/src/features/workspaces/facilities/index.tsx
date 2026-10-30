import type { ComponentType } from 'react'
import { AnalyticsScreen } from '@/features/analytics/AnalyticsScreen'
import { ApprovalsScreen } from '@/features/approvals/ApprovalsScreen'
import { AuditScreen } from '@/features/audit/AuditScreen'
import { CampusMapScreen } from '@/features/campus/CampusMapScreen'
import { CollisionReviewScreen, SimulatorScreen } from '@/features/collision/CollisionScreens'
import { CommandCentreScreen } from '@/features/dashboard/OverviewScreens'
import { IncidentsScreen } from '@/features/incidents/IncidentsScreen'
import { InboxScreen } from '@/features/intake/InboxScreen'
import { InventoryScreen } from '@/features/inventory/InventoryScreen'
import { SlaScreen } from '@/features/sla/SlaScreen'
import { TechniciansScreen } from '@/features/workorders/TechniciansScreen'
import { WorkOrderBoard } from '@/features/workorders/WorkOrderBoard'

/** Facilities Administrator workspace: the campus-wide command centre. */
export const screens: Record<string, ComponentType> = {
  'fac.command': CommandCentreScreen,
  'fac.map': () => <CampusMapScreen title="Live Campus Map" description="Incidents, closures and impact zones on the campus." />,
  'fac.inbox': InboxScreen,
  'fac.triage': () => <IncidentsScreen variant="triage" title="Incident Triage" description="Duplicate clusters, correlation, summaries and assignment in one queue." />,
  'fac.workOrders': () => <WorkOrderBoard title="Work Orders" description="The full lifecycle board. Open a card to assign or reassign." />,
  'fac.technicians': TechniciansScreen,
  'fac.collision': CollisionReviewScreen,
  'fac.simulator': SimulatorScreen,
  'fac.inventory': () => <InventoryScreen title="Inventory" description="Campus stock and reservations." />,
  'fac.approvals': () => <ApprovalsScreen mode="all" title="Approvals" description="Costly repairs and overrides within your authority." />,
  'fac.sla': () => <SlaScreen title="SLA Monitor" description="At-risk and breached work, with the early warning." />,
  'fac.analytics': () => <AnalyticsScreen title="Analytics" description="Open requests, SLA compliance, utilisation, shortages and recurring incidents." />,
  'fac.audit': () => <AuditScreen title="Audit Trail" description="Operational decisions: who did what, when, and why." />,
}

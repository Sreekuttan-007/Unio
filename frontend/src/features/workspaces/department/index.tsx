import type { ComponentType } from 'react'
import { AnalyticsScreen } from '@/features/analytics/AnalyticsScreen'
import { ApprovalsScreen } from '@/features/approvals/ApprovalsScreen'
import { MyBookingsScreen } from '@/features/bookings/BookingScreens'
import { ResourcesScreen } from '@/features/campus/ResourcesScreen'
import { DeptOverviewScreen } from '@/features/dashboard/OverviewScreens'
import { IncidentsScreen } from '@/features/incidents/IncidentsScreen'
import { InventoryScreen } from '@/features/inventory/InventoryScreen'
import { SlaScreen } from '@/features/sla/SlaScreen'
import { WorkOrderBoard } from '@/features/workorders/WorkOrderBoard'

/** Department Manager workspace: department-scoped control. */
export const screens: Record<string, ComponentType> = {
  'dept.overview': DeptOverviewScreen,
  'dept.incidents': () => <IncidentsScreen variant="department" title="Department Incidents" description="Triage and prioritise incidents within your department." />,
  'dept.workRequests': () => <WorkOrderBoard title="Work Requests" description="Create and reassign work within your authority. Assignment is checked against skills, shifts and workload." />,
  'dept.resources': ResourcesScreen,
  'dept.bookings': () => <MyBookingsScreen title="Room Bookings" description="Department bookings and any conflicts." />,
  'dept.inventory': () => <InventoryScreen title="Inventory" description="Department stock, what is reserved, and shortages." />,
  'dept.approvals': () => <ApprovalsScreen mode="mine" title="Approvals" description="Raise purchase and costly-repair requests. You can never approve your own, and above your limit it goes to Procurement." />,
  'dept.sla': () => <SlaScreen title="SLA & Escalations" description="Compliance, overdue work and escalation history for your department." />,
  'dept.analytics': () => <AnalyticsScreen title="Analytics" description="Utilisation and recurring incidents in your department." />,
}

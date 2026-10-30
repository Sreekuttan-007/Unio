import type { ComponentType } from 'react'
import { ApprovalsScreen } from '@/features/approvals/ApprovalsScreen'
import { AuditScreen } from '@/features/audit/AuditScreen'
import { ProcOverviewScreen } from '@/features/dashboard/OverviewScreens'
import { GoodsReceiptsScreen, InvoicesScreen, PurchaseOrdersScreen } from '@/features/procurement/ProcurementScreens'

/** Procurement Approver workspace: purchase and financial control. */
export const screens: Record<string, ComponentType> = {
  'proc.overview': ProcOverviewScreen,
  'proc.queue': () => <ApprovalsScreen mode="queue" title="Approval Queue" description="Requests waiting for your decision, with the evidence beside them." />,
  'proc.requests': () => <ApprovalsScreen mode="all" title="Requests" description="Every approval request, with its status." />,
  'proc.orders': PurchaseOrdersScreen,
  'proc.invoices': () => <InvoicesScreen focus="all" />,
  'proc.discrepancies': () => <InvoicesScreen focus="discrepancies" />,
  'proc.receipts': GoodsReceiptsScreen,
  'proc.history': () => <AuditScreen title="History" description="Procurement decisions and stock movements, with who made them." />,
}

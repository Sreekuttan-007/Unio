import type { Approval, GoodsReceipt, Invoice, PurchaseOrder, StockRow } from '@/types/domain'
import { campus } from './campus'
import type { Clock } from './helpers'

export function buildStock(): StockRow[] {
  const reserved: Record<string, number> = { 'ITM-LED-TUBE-18W': 4, 'ITM-HDMI-5M': 1, 'ITM-PROJ-LAMP': 0 }
  const blocked: Record<string, number> = { 'ITM-MCB-32A-3P': 1 }
  return campus.items.map((item) => {
    const hold = reserved[item.id] ?? 0
    const available = Math.max(0, item.onHand - hold)
    return {
      id: item.id,
      sku: item.sku,
      name: item.name,
      category: item.category,
      unit: item.unit,
      onHand: item.onHand,
      reserved: hold,
      available,
      threshold: item.reorderThreshold,
      critical: item.critical,
      location: 'All stores',
      status: item.onHand === 0 ? 'OUT' : item.onHand <= item.reorderThreshold ? 'LOW' : 'OK',
      blockedWorkOrders: blocked[item.id] ?? 0,
    }
  })
}

export function buildApprovals(clock: Clock): Approval[] {
  const { at } = clock
  return [
    {
      id: 'APR-610',
      type: 'PURCHASE',
      status: 'UNDER_REVIEW',
      title: 'Buy 2 x MCB 32A three-pole breakers for the ARB floor 2 panel',
      requesterName: 'Meera Iyer',
      requesterRole: 'DEPARTMENT_MANAGER',
      amountPaise: 290000,
      justification: 'WO-212 cannot proceed: the breaker that tripped is out of stock and the floor 2 exam room has no power. One for the repair and one spare, because this panel has tripped before.',
      linkedWorkOrderId: 'WO-212',
      linkedIncidentId: 'INC-1041',
      lines: [{ name: 'MCB 32A three pole', qty: 2, estimatePaise: 145000 }],
      evidence: [
        { label: 'Stock on hand', value: '0 across all stores', tone: 'danger' },
        { label: 'Needed by WO-212', value: '1 breaker, reserved when it arrives', tone: 'warning' },
        { label: 'Work order SLA', value: 'At risk, 52 min left', tone: 'warning' },
        { label: 'Last purchase', value: '14 weeks ago at the same price', tone: 'success' },
        { label: 'Supplier', value: 'Brightline Electricals (approved)' },
      ],
      routing: 'Under the ₹5,00,000 Procurement limit. Needs a Procurement Approver.',
      decisions: [],
      createdAt: at(-30),
      availableActions: [
        { key: 'approval.approve', label: 'Approve' },
        { key: 'approval.reject', label: 'Reject' },
        { key: 'approval.clarify', label: 'Ask for clarification' },
      ],
      unavailableActions: [],
    },
    {
      id: 'APR-608',
      type: 'COSTLY_REPAIR',
      status: 'SUBMITTED',
      title: 'Replace the air conditioner compressor in lab RLB-102',
      requesterName: 'Vikram Shetty',
      requesterRole: 'DEPARTMENT_MANAGER',
      amountPaise: 4800000,
      justification: 'Third failure this quarter. A repair estimate of ₹48,000 includes the compressor and refrigerant.',
      linkedWorkOrderId: 'WO-214',
      linkedIncidentId: 'INC-1034',
      lines: [
        { name: 'AC compressor 1.5 ton', qty: 1, estimatePaise: 1480000 },
        { name: 'Labour and refrigerant', qty: 1, estimatePaise: 3320000 },
      ],
      evidence: [
        { label: 'Repeat faults on this asset', value: '3 in 6 months', tone: 'warning' },
        { label: 'Sessions using this lab', value: '4 per week, 120 students' },
        { label: 'Repair vs replace', value: 'Repair is 61% of unit cost' },
      ],
      routing: 'Above the ₹25,000 Department Manager limit, so routed up to Facilities or Procurement.',
      decisions: [],
      createdAt: at(-140),
      availableActions: [
        { key: 'approval.approve', label: 'Approve' },
        { key: 'approval.reject', label: 'Reject' },
        { key: 'approval.clarify', label: 'Ask for clarification' },
      ],
      unavailableActions: [],
    },
    {
      id: 'APR-605',
      type: 'OVERRIDE',
      status: 'EXECUTED',
      title: 'Allow a third concurrent task for Ravi Kumar',
      requesterName: 'Arjun Menon',
      requesterRole: 'FACILITIES_ADMIN',
      amountPaise: 0,
      justification: 'Only electrician on shift until noon. Meena Das arrives at 12:00.',
      linkedWorkOrderId: 'WO-216',
      linkedIncidentId: null,
      lines: [],
      evidence: [{ label: 'Collision warning', value: 'TECH_WORKLOAD, a soft rule' }],
      routing: 'Soft collisions can be overridden with a reason. Hard collisions cannot.',
      decisions: [{ by: 'Arjun Menon', decision: 'APPROVED', reason: 'Only electrician on shift. Meena Das arrives at noon.', at: at(-55) }],
      createdAt: at(-56),
      availableActions: [],
      unavailableActions: [],
    },
    {
      id: 'APR-601',
      type: 'PURCHASE',
      status: 'APPROVED',
      title: 'Buy 4 x Wi-Fi 6 access points',
      requesterName: 'Meera Iyer',
      requesterRole: 'DEPARTMENT_MANAGER',
      amountPaise: 3920000,
      justification: 'Replace the two failing access points on ARB floor 2 and keep two spare.',
      linkedWorkOrderId: null,
      linkedIncidentId: null,
      lines: [{ name: 'Wi-Fi 6 access point', qty: 4, estimatePaise: 980000 }],
      evidence: [{ label: 'Repeat faults', value: 'AP ARB-F2-2 failed 6 times in 6 months', tone: 'warning' }],
      routing: 'Approved by Procurement. Ordered as PO-881.',
      decisions: [{ by: 'Divya Pillai', decision: 'APPROVED', reason: 'Recurring failures justify the replacement.', at: at(-2880) }],
      createdAt: at(-3000),
      availableActions: [],
      unavailableActions: [],
    },
  ]
}

export function buildPurchaseOrders(clock: Clock): PurchaseOrder[] {
  const { at } = clock
  return [
    { id: 'PO-881', approvalId: 'APR-601', supplier: 'Brightline Networks', totalPaise: 3920000, status: 'ORDERED', orderedAt: at(-2800), lines: [{ sku: 'AP-WIFI6', name: 'Wi-Fi 6 access point', qty: 4, unitPaise: 980000, received: 0 }] },
    { id: 'PO-879', approvalId: 'APR-596', supplier: 'Brightline Electricals', totalPaise: 580000, status: 'RECEIVED', orderedAt: at(-9000), lines: [{ sku: 'MCB-16A-1P', name: 'MCB 16A single pole', qty: 20, unitPaise: 18000, received: 20 }, { sku: 'FUSE-10A', name: 'Fuse 10A', qty: 50, unitPaise: 2500, received: 50 }] },
  ]
}

export function buildInvoices(): Invoice[] {
  return [
    {
      id: 'INV-431',
      supplier: 'Brightline Networks',
      invoiceNumber: 'BN/2026/0447',
      invoiceDate: '2026-10-28',
      purchaseOrderId: 'PO-881',
      status: 'DISCREPANCY',
      totalPaise: 4344000,
      fileName: 'brightline-bn-0447.pdf',
      extractionSource: 'AI',
      lines: [
        { lineNo: 1, description: 'Wi-Fi 6 access point', qty: 4, unitPaise: 1040000, poQty: 4, poUnitPaise: 980000, match: 'PRICE', confidence: 0.97 },
        { lineNo: 2, description: 'Installation and configuration', qty: 1, unitPaise: 184000, poQty: null, poUnitPaise: null, match: 'EXTRA', confidence: 0.88 },
      ],
      discrepancies: [
        { code: 'PRICE_MISMATCH', message: 'Line 1 is ₹10,400 each. The purchase order says ₹9,800, a difference of ₹2,400 in total.', resolved: false },
        { code: 'EXTRA_LINE', message: 'Line 2 (installation, ₹1,840) is not on the purchase order.', resolved: false },
      ],
    },
    {
      id: 'INV-428',
      supplier: 'Brightline Electricals',
      invoiceNumber: 'BE/2026/1190',
      invoiceDate: '2026-10-22',
      purchaseOrderId: 'PO-879',
      status: 'MATCHED',
      totalPaise: 580000,
      fileName: 'brightline-be-1190.pdf',
      extractionSource: 'AI',
      lines: [
        { lineNo: 1, description: 'MCB 16A single pole', qty: 20, unitPaise: 18000, poQty: 20, poUnitPaise: 18000, match: 'OK', confidence: 0.99 },
        { lineNo: 2, description: 'Fuse 10A', qty: 50, unitPaise: 2500, poQty: 50, poUnitPaise: 2500, match: 'OK', confidence: 0.98 },
      ],
      discrepancies: [],
    },
    {
      id: 'INV-420',
      supplier: 'Metro Plumbing Supplies',
      invoiceNumber: 'MP-7781',
      invoiceDate: '2026-10-10',
      purchaseOrderId: 'PO-868',
      status: 'POSTED',
      totalPaise: 192000,
      fileName: 'metro-mp-7781.pdf',
      extractionSource: 'MANUAL',
      lines: [{ lineNo: 1, description: 'Tap 15mm', qty: 8, unitPaise: 24000, poQty: 8, poUnitPaise: 24000, match: 'OK', confidence: 1 }],
      discrepancies: [],
    },
  ]
}

export function buildReceipts(clock: Clock): GoodsReceipt[] {
  return [
    { id: 'GR-92', purchaseOrderId: 'PO-881', invoiceId: 'INV-431', status: 'PENDING', receivedAt: clock.at(-240), lines: [{ name: 'Wi-Fi 6 access point', ordered: 4, received: 4 }] },
    { id: 'GR-90', purchaseOrderId: 'PO-879', invoiceId: 'INV-428', status: 'PENDING', receivedAt: clock.at(-5000), lines: [{ name: 'MCB 16A single pole', ordered: 20, received: 20 }, { name: 'Fuse 10A', ordered: 50, received: 50 }] },
  ]
}

import { FileText } from 'lucide-react'
import { useState } from 'react'
import { Badge, Banner, Button, Card, CardBody, CardHeader, DataTable, Dropzone, ListRow, PageHeader, ProgressBar, StatTile, type Column, type Tone } from '@/ui'
import type { GoodsReceipt, Invoice, InvoiceLine, PurchaseOrder } from '@/types/domain'
import { describeError } from '../shared/errors'
import { readAsUpload } from '../shared/files'
import { ago, money, titleCase } from '../shared/format'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useAction, useApi } from '../shared/useApi'

export function PurchaseOrdersScreen() {
  const orders = useApi<PurchaseOrder[]>('/purchase-orders')
  const TONE: Record<PurchaseOrder['status'], Tone> = { ORDERED: 'info', PARTIALLY_RECEIVED: 'warning', RECEIVED: 'success' }
  return (
    <div className="space-y-5">
      <PageHeader title="Purchase Orders" description="What was ordered, from whom, and how much has arrived." />
      <QueryBoundary query={orders} isEmpty={(items) => items.length === 0} emptyTitle="No purchase orders">
        {(items) => (
          <ul className="space-y-3">
            {items.map((order) => {
              const ordered = order.lines.reduce((sum, line) => sum + line.qty, 0)
              const received = order.lines.reduce((sum, line) => sum + line.received, 0)
              return (
                <li key={order.id}>
                  <Card>
                    <CardBody className="space-y-3">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div><p className="font-semibold text-ink">{order.id} · {order.supplier}</p><p className="text-xs text-muted">From request {order.approvalId} · {ago(order.orderedAt)}</p></div>
                        <span className="flex items-center gap-2"><span className="font-medium tabular-nums">{money(order.totalPaise)}</span><Badge tone={TONE[order.status]}>{titleCase(order.status)}</Badge></span>
                      </div>
                      <ProgressBar label={`Received ${received} of ${ordered}`} value={(received / ordered) * 100} tone={received === ordered ? 'success' : 'info'} />
                      <ul className="text-sm text-muted">{order.lines.map((line) => <li key={line.sku}>{line.qty} x {line.name} at {money(line.unitPaise)}</li>)}</ul>
                    </CardBody>
                  </Card>
                </li>
              )
            })}
          </ul>
        )}
      </QueryBoundary>
    </div>
  )
}

const MATCH: Record<InvoiceLine['match'], { tone: Tone; label: string }> = {
  OK: { tone: 'success', label: 'Matches' },
  QTY: { tone: 'warning', label: 'Quantity differs' },
  PRICE: { tone: 'danger', label: 'Price differs' },
  EXTRA: { tone: 'warning', label: 'Not on the order' },
}

const INVOICE_STATUS: Record<Invoice['status'], Tone> = { EXTRACTED: 'info', DISCREPANCY: 'danger', MATCHED: 'success', VALIDATED: 'success', POSTED: 'neutral' }

function InvoiceReview({ invoice }: { invoice: Invoice }) {
  const [error, setError] = useState<string | null>(null)
  const resolve = useAction<{ code: string }, Invoice>('POST', `/invoices/${invoice.id}/resolve`, ['/invoices'])
  const validate = useAction<Record<string, never>, Invoice>('POST', `/invoices/${invoice.id}/validate`, ['/invoices'])

  const columns: Column<InvoiceLine>[] = [
    { key: 'item', header: 'Line', cell: (line) => <span>{line.lineNo}. {line.description}</span> },
    { key: 'qty', header: 'Invoice qty', className: 'text-right tabular-nums', cell: (line) => `${line.qty}${line.poQty !== null && line.poQty !== line.qty ? ` (order ${line.poQty})` : ''}` },
    { key: 'price', header: 'Unit price', className: 'text-right tabular-nums', cell: (line) => `${money(line.unitPaise)}${line.poUnitPaise !== null && line.poUnitPaise !== line.unitPaise ? ` (order ${money(line.poUnitPaise)})` : ''}` },
    { key: 'match', header: 'Check', cell: (line) => <Badge tone={MATCH[line.match].tone}>{MATCH[line.match].label}</Badge> },
    { key: 'conf', header: 'Read confidence', className: 'text-right tabular-nums', cell: (line) => `${Math.round(line.confidence * 100)}%` },
  ]

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-[16rem_1fr]">
        <Card>
          <CardBody className="space-y-2 text-center">
            <FileText aria-hidden="true" className="mx-auto size-10 text-muted" />
            <p className="break-all text-sm font-medium text-ink">{invoice.fileName}</p>
            <p className="text-xs text-muted">The original stays beside the extracted values, so you can check them.</p>
            <Badge tone={invoice.extractionSource === 'AI' ? 'accent' : 'neutral'}>{invoice.extractionSource === 'AI' ? 'Read by AI' : 'Typed in by hand'}</Badge>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title={`${invoice.supplier} · ${invoice.invoiceNumber}`} description={`Dated ${invoice.invoiceDate} · matched against ${invoice.purchaseOrderId}`} action={<Badge tone={INVOICE_STATUS[invoice.status]}>{titleCase(invoice.status)}</Badge>} />
          <DataTable caption="Invoice lines" columns={columns} rows={invoice.lines} rowKey={(line) => String(line.lineNo)} />
          <p className="border-t border-line px-4 py-3 text-right text-sm">Invoice total <span className="font-semibold tabular-nums">{money(invoice.totalPaise)}</span></p>
        </Card>
      </div>

      {invoice.discrepancies.map((item) => (
        <Banner key={item.code} tone={item.resolved ? 'success' : 'danger'} title={item.resolved ? 'Resolved' : 'Needs a decision'} action={!item.resolved ? <Button variant="secondary" compact loading={resolve.isPending} onClick={() => resolve.mutate({ code: item.code })}>{item.code === 'PRICE_MISMATCH' ? 'Hold to the order price' : 'Reject this line'}</Button> : undefined}>
          {item.message}
        </Banner>
      ))}
      {error ? <Banner tone="danger" title="Cannot validate yet" role="alert">{error}</Banner> : null}
      {['DISCREPANCY', 'MATCHED'].includes(invoice.status) ? (
        <div className="flex flex-wrap items-center gap-3">
          <Button loading={validate.isPending} onClick={() => validate.mutate({}, { onError: (failure) => setError(describeError(failure)), onSuccess: () => setError(null) })}>Validate this invoice</Button>
          <span className="text-xs text-muted">Validating does not change stock. Only a goods receipt does.</span>
        </div>
      ) : null}
    </div>
  )
}

export function InvoicesScreen({ focus }: { focus: 'all' | 'discrepancies' }) {
  const invoices = useApi<Invoice[]>('/invoices')
  const [openId, setOpenId] = useState<string | null>(focus === 'discrepancies' ? 'INV-431' : null)
  const upload = useAction<{ fileName: string; mime: string; contentBase64: string }, Invoice>('POST', '/invoices', ['/invoices'], { idempotent: true })
  const [uploadError, setUploadError] = useState<string | null>(null)
  const send = async (file: File) => {
    setUploadError(null)
    try {
      const picked = await readAsUpload(file)
      const invoice = await upload.mutateAsync({ fileName: picked.name, mime: picked.mime, contentBase64: picked.contentBase64 })
      setOpenId(invoice.id)
    } catch (failure) {
      setUploadError(describeError(failure))
    }
  }
  const title = focus === 'all' ? 'Invoices' : 'Discrepancies'

  return (
    <div className="space-y-5">
      <PageHeader title={title} description={focus === 'all' ? 'Upload an invoice and review what was read from it. Uploading never changes stock.' : 'Where an invoice disagrees with its purchase order.'} />
      {focus === 'all' ? <Dropzone label="Upload an invoice" hint="PDF or a photo. It is read, then checked against the purchase order." accept="application/pdf,text/plain,image/*" onFiles={(files) => files[0] && void send(files[0])} /> : null}
      {uploadError ? <Banner tone="danger" title="The invoice was not read" role="alert">{uploadError}</Banner> : null}
      {upload.isPending ? <Banner tone="info" title="Reading the invoice" role="status">Extracting the supplier, number and lines, then matching them to the order.</Banner> : null}
      <QueryBoundary query={invoices} isEmpty={(items) => items.length === 0} emptyTitle="No invoices">
        {(items) => {
          const visible = items.filter((item) => focus === 'all' || item.status === 'DISCREPANCY' || item.discrepancies.length > 0)
          const open = visible.find((item) => item.id === openId) ?? visible[0]
          return (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                <StatTile label="Invoices" value={items.length} />
                <StatTile label="With discrepancies" value={items.filter((item) => item.status === 'DISCREPANCY').length} tone="danger" />
                <StatTile label="Posted to stock" value={items.filter((item) => item.status === 'POSTED').length} tone="success" />
              </div>
              <Card>
                {visible.map((invoice) => (
                  <ListRow key={invoice.id} testId={`invoice-${invoice.id}`} selected={invoice.id === open?.id} onClick={() => setOpenId(invoice.id)} title={`${invoice.supplier} · ${invoice.invoiceNumber}`} subtitle={`${invoice.id} · ${invoice.purchaseOrderId}`} meta={money(invoice.totalPaise)} trailing={<Badge tone={INVOICE_STATUS[invoice.status]}>{titleCase(invoice.status)}</Badge>} />
                ))}
              </Card>
              {open ? <InvoiceReview key={open.id} invoice={open} /> : null}
            </>
          )
        }}
      </QueryBoundary>
    </div>
  )
}

interface PostResult {
  posted: boolean
  replayed: boolean
  ledgerEntries: { sku: string; qty: number }[]
  message: string
}

export function GoodsReceiptsScreen() {
  const receipts = useApi<GoodsReceipt[]>('/goods-receipts')
  const validate = useAction<{ id: string }, PostResult>('POST', (job) => `/goods-receipts/${job.id}/validate`, ['/goods-receipts', '/invoices', '/inventory'])
  const [results, setResults] = useState<Record<string, PostResult | string>>({})

  const run = async (id: string) => {
    try {
      const posted = await validate.mutateAsync({ id })
      setResults((current) => ({ ...current, [id]: posted }))
    } catch (failure) {
      setResults((current) => ({ ...current, [id]: describeError(failure) }))
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader title="Goods Receipts" description="Validate what arrived. This is the only action that increases stock, and doing it twice posts once." />
      <QueryBoundary query={receipts} isEmpty={(items) => items.length === 0} emptyTitle="Nothing to receive">
        {(items) => (
          <ul className="space-y-3">
            {items.map((receipt) => {
              const result = results[receipt.id]
              return (
                <li key={receipt.id}>
                  <Card data-testid={`receipt-${receipt.id}`}>
                    <CardBody className="space-y-3">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div><p className="font-semibold text-ink">{receipt.id} · {receipt.purchaseOrderId}</p><p className="text-xs text-muted">Arrived {ago(receipt.receivedAt)}{receipt.invoiceId ? ` · invoice ${receipt.invoiceId}` : ''}</p></div>
                        <Badge tone={receipt.status === 'VALIDATED' ? 'success' : 'warning'}>{receipt.status === 'VALIDATED' ? 'Posted' : 'Waiting for you'}</Badge>
                      </div>
                      <ul className="text-sm text-ink">{receipt.lines.map((line) => <li key={line.name}>{line.received} of {line.ordered} x {line.name}</li>)}</ul>
                      {typeof result === 'string' ? <Banner tone="danger" title="Not posted" role="alert">{result}</Banner> : null}
                      {result && typeof result !== 'string' ? (
                        <Banner tone={result.replayed ? 'info' : 'success'} title={result.replayed ? 'Already posted, nothing changed' : 'Stock posted'} role="status">
                          {result.message} {result.ledgerEntries.map((entry) => `+${entry.qty} ${entry.sku}`).join(', ')}.
                        </Banner>
                      ) : null}
                      <Button variant={receipt.status === 'VALIDATED' ? 'ghost' : 'primary'} loading={validate.isPending} onClick={() => void run(receipt.id)}>
                        {receipt.status === 'VALIDATED' ? 'Validate again (safe to repeat)' : 'Validate and post to stock'}
                      </Button>
                    </CardBody>
                  </Card>
                </li>
              )
            })}
          </ul>
        )}
      </QueryBoundary>
    </div>
  )
}

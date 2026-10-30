import { CheckCircle2, MessageSquare, FileText, Sparkles } from 'lucide-react'
import { useState } from 'react'
import {
  Badge, Banner, Button, Card, CardBody, CardHeader, ChatComposer, ChatThread, Dropzone, PageHeader, SegmentedControl, SelectField, TextArea, TextField,
  type ChatMessage,
} from '@/ui'
import type { Category, Extraction, ReportSummary } from '@/types/domain'
import { describeError } from '../shared/errors'
import { titleCase } from '../shared/format'
import { useAction } from '../shared/useApi'
import { useNavTo } from '../shared/useNavTo'

const CATEGORIES: Category[] = ['ELECTRICAL', 'NETWORK', 'PLUMBING', 'HVAC', 'CARPENTRY', 'EQUIPMENT', 'HOUSEKEEPING', 'SAFETY', 'OTHER']
const URGENCIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const
const IMPACTS = [
  { value: '', label: 'No effect on teaching' },
  { value: 'LECTURE', label: 'A lecture' },
  { value: 'PRACTICAL', label: 'A practical' },
  { value: 'EXAM', label: 'An exam' },
  { value: 'EVENT', label: 'An event' },
]

function Understood({
  extraction,
  onChange,
  onClarify,
  academicImpact,
  impact,
  onImpact,
}: {
  extraction: Extraction
  onChange: (next: Extraction) => void
  onClarify: (answer: string) => void
  academicImpact: boolean
  impact: string
  onImpact: (value: string) => void
}) {
  const [answer, setAnswer] = useState('')
  return (
    <Card>
      <CardHeader
        title="Here is what we understood"
        description="Fix anything that is wrong before you send it."
        action={
          <Badge tone="accent" icon={<Sparkles aria-hidden="true" className="size-3" />}>
            {extraction.source === 'AI' ? `AI suggestion, ${Math.round(extraction.categoryConfidence * 100)}% sure` : 'Suggested by rules'}
          </Badge>
        }
      />
      <CardBody className="space-y-4">
        {extraction.duplicate ? (
          <Banner tone="info" title={`This looks like ${extraction.duplicate.incidentId}`}>
            “{extraction.duplicate.title}” already has {extraction.duplicate.reportCount} reports. Yours will be added to it, and you will see the same status updates.
          </Banner>
        ) : null}
        {extraction.clarification ? (
          <Banner tone="warning" title="One thing is missing" role="status">
            <p>{extraction.clarification}</p>
            <div className="mt-3 flex flex-wrap items-end gap-2">
              <div className="min-w-48 flex-1">
                <TextField label="Your answer" value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="ARB-204" />
              </div>
              <Button variant="secondary" disabled={!answer.trim()} onClick={() => onClarify(answer.trim())}>Add</Button>
            </div>
          </Banner>
        ) : null}
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectField label="Issue type" value={extraction.category} onChange={(event) => onChange({ ...extraction, category: event.target.value as Category })} options={CATEGORIES.map((value) => ({ value, label: titleCase(value) }))} />
          <SelectField label="How urgent" value={extraction.urgency} onChange={(event) => onChange({ ...extraction, urgency: event.target.value as Extraction['urgency'] })} options={URGENCIES.map((value) => ({ value, label: titleCase(value) }))} />
          <TextField label="Where" value={extraction.location.text} onChange={(event) => onChange({ ...extraction, location: { ...extraction.location, text: event.target.value } })} hint="Room and building" />
          <TextField label="What is affected" value={extraction.asset ?? ''} onChange={(event) => onChange({ ...extraction, asset: event.target.value || null })} hint="Optional, such as Projector" />
          {academicImpact ? <SelectField label="Does this affect teaching" value={impact} onChange={(event) => onImpact(event.target.value)} options={IMPACTS} /> : null}
        </div>
      </CardBody>
    </Card>
  )
}

function Done({ report }: { report: ReportSummary }) {
  const { go, pathOf } = useNavTo()
  const tracks = pathOf('student.myReports') !== null
  return (
    <Card>
      <CardBody className="flex flex-col items-center gap-3 py-10 text-center">
        <CheckCircle2 aria-hidden="true" className="size-12 text-success" />
        <h2 className="text-xl font-semibold text-ink">Report {report.id} sent</h2>
        <p className="max-w-prose text-sm text-muted">{report.summary}</p>
        <p className="text-xs text-muted">Incident {report.incidentId} · priority {report.priority}</p>
        <Button onClick={() => go(tracks ? 'student.myReports' : 'faculty.home')}>{tracks ? 'Track my reports' : 'Back to home'}</Button>
      </CardBody>
    </Card>
  )
}

export function ReportIssueScreen({ academicImpact = false }: { academicImpact?: boolean }) {
  const [mode, setMode] = useState<'form' | 'chat'>('form')
  const [text, setText] = useState('')
  const [room, setRoom] = useState('')
  const [photos, setPhotos] = useState<File[]>([])
  const [impact, setImpact] = useState('')
  const [extraction, setExtraction] = useState<Extraction | null>(null)
  const [report, setReport] = useState<ReportSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: 'hello', from: 'assistant', text: 'Hi. Tell me what is wrong and where, in your own words.' },
  ])
  const [typing, setTyping] = useState(false)

  const extract = useAction<{ text: string }, Extraction>('POST', '/issues/extract')
  const submit = useAction<{ text: string; extraction: Extraction; channel: 'FORM' | 'CHAT'; academicImpact?: string }, ReportSummary>('POST', '/issues', ['/issues/mine'], { idempotent: true })

  const fullText = [text.trim(), room.trim()].filter(Boolean).join(' ')

  const check = async () => {
    setError(null)
    try {
      setExtraction(await extract.mutateAsync({ text: fullText }))
    } catch (failure) {
      setError(describeError(failure))
    }
  }

  const send = async () => {
    if (!extraction) return
    setError(null)
    try {
      setReport(await submit.mutateAsync({ text: fullText, extraction, channel: mode === 'chat' ? 'CHAT' : 'FORM', academicImpact: impact || undefined }))
    } catch (failure) {
      setError(describeError(failure))
    }
  }

  const clarify = async (answer: string) => {
    setText((current) => `${current} ${answer}`)
    setExtraction(await extract.mutateAsync({ text: `${fullText} ${answer}` }))
  }

  const chatSend = async (message: string) => {
    const combined = `${text} ${message}`.trim()
    setText(combined)
    setMessages((current) => [...current, { id: `u${current.length}`, from: 'user', text: message }])
    setTyping(true)
    try {
      const understood = await extract.mutateAsync({ text: combined })
      setExtraction(understood)
      const summary = `I read this as a ${titleCase(understood.category).toLowerCase()} problem${understood.location.text ? ` in ${understood.location.text}` : ''}, ${titleCase(understood.urgency).toLowerCase()} urgency.`
      const extra = understood.duplicate ? ` It matches ${understood.duplicate.incidentId}, which ${understood.duplicate.reportCount} people have already reported, so I will add yours to it.` : ''
      setMessages((current) => [
        ...current,
        understood.clarification
          ? { id: `a${current.length}`, from: 'assistant', text: `${summary} ${understood.clarification}` }
          : { id: `a${current.length}`, from: 'assistant', text: `${summary}${extra} Shall I send it?`, choices: ['Send it', 'Start over'] },
      ])
    } catch (failure) {
      setMessages((current) => [...current, { id: `e${current.length}`, from: 'assistant', text: describeError(failure) }])
    } finally {
      setTyping(false)
    }
  }

  const chatChoice = async (choice: string) => {
    if (choice === 'Start over') {
      setText('')
      setExtraction(null)
      setMessages([{ id: 'hello2', from: 'assistant', text: 'No problem. What is wrong?' }])
      return
    }
    setMessages((current) => [...current, { id: `u${current.length}`, from: 'user', text: choice }])
    await send()
  }

  if (report) return (<div><PageHeader title="Report Issue" /><Done report={report} /></div>)

  return (
    <div className="space-y-6">
      <PageHeader title="Report Issue" description="Describe the problem in your own words. We work out the rest and you confirm it." actions={<SegmentedControl label="How to report" value={mode} onChange={(value) => { setMode(value); setExtraction(null) }} options={[{ value: 'form', label: 'Form' }, { value: 'chat', label: 'Chat' }]} />} />

      {error ? <Banner tone="danger" title="That did not work" role="alert">{error}</Banner> : null}

      {mode === 'form' ? (
        <>
          <Card>
            <CardHeader title="What is wrong" action={<FileText aria-hidden="true" className="size-5 text-muted" />} />
            <CardBody className="space-y-4">
              <TextArea label="Describe it" value={text} onChange={(event) => setText(event.target.value)} placeholder="Wi-Fi is not working in ARB-204 and we have an exam" hint="Say where it is and what you see. Names of rooms such as ARB-204 help." />
              <TextField label="Room or place" value={room} onChange={(event) => setRoom(event.target.value)} placeholder="Optional, such as ARB-204" />
              <Dropzone label="Add a photo" hint={photos.length ? `${photos.length} photo added: ${photos.map((file) => file.name).join(', ')}` : 'Take one with your camera or choose from your gallery'} accept="image/*" capture onFiles={setPhotos} />
              <Button loading={extract.isPending} disabled={fullText.length < 6} onClick={() => void check()}>Check my report</Button>
            </CardBody>
          </Card>
          {extraction ? (
            <>
              <Understood extraction={extraction} onChange={setExtraction} onClarify={(answer) => void clarify(answer)} academicImpact={academicImpact} impact={impact} onImpact={setImpact} />
              <div className="flex flex-wrap gap-3">
                <Button loading={submit.isPending} disabled={!!extraction.clarification} onClick={() => void send()}>Send report</Button>
                <Button variant="ghost" onClick={() => setExtraction(null)}>Edit</Button>
              </div>
            </>
          ) : null}
        </>
      ) : (
        <Card>
          <CardHeader title="Chat" action={<MessageSquare aria-hidden="true" className="size-5 text-muted" />} />
          <CardBody className="space-y-4">
            <ChatThread messages={messages} typing={typing} onChoose={(choice) => void chatChoice(choice)} />
            <ChatComposer onSend={(message) => void chatSend(message)} disabled={typing || submit.isPending} />
          </CardBody>
        </Card>
      )}
    </div>
  )
}

import { SendHorizontal, Sparkles } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { cn } from './cn'

export interface ChatMessage {
  id: string
  from: 'user' | 'assistant'
  text: string
  /** Quick replies the assistant offers, such as a list of rooms. */
  choices?: string[]
  extra?: ReactNode
}

export function ChatThread({ messages, typing, onChoose }: { messages: ChatMessage[]; typing?: boolean; onChoose?: (choice: string) => void }) {
  return (
    <div className="space-y-3" role="log" aria-live="polite" aria-label="Conversation">
      {messages.map((message) => (
        <div key={message.id} className={cn('flex gap-2', message.from === 'user' && 'justify-end')}>
          {message.from === 'assistant' ? (
            <span aria-hidden="true" className="mt-1 grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-accent-ink">
              <Sparkles className="size-4" />
            </span>
          ) : null}
          <div className="max-w-[85%] space-y-2">
            <p className={cn('rounded-lg px-3.5 py-2.5 text-sm', message.from === 'user' ? 'bg-accent text-accent-contrast' : 'bg-surface-2 text-ink')}>{message.text}</p>
            {message.choices?.length ? (
              <div className="flex flex-wrap gap-2">
                {message.choices.map((choice) => (
                  <button key={choice} type="button" onClick={() => onChoose?.(choice)} className="min-h-10 rounded-full border border-line-strong bg-surface px-3 text-sm text-ink hover:border-accent hover:bg-accent-soft">
                    {choice}
                  </button>
                ))}
              </div>
            ) : null}
            {message.extra}
          </div>
        </div>
      ))}
      {typing ? (
        <p className="pl-9 text-xs text-muted" role="status">
          Thinking...
        </p>
      ) : null}
    </div>
  )
}

export function ChatComposer({ onSend, disabled, placeholder = 'Describe the problem' }: { onSend: (text: string) => void; disabled?: boolean; placeholder?: string }) {
  const [text, setText] = useState('')
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!text.trim()) return
    onSend(text.trim())
    setText('')
  }
  return (
    <form onSubmit={submit} className="flex items-center gap-2">
      <input
        value={text}
        onChange={(event) => setText(event.target.value)}
        disabled={disabled}
        placeholder={placeholder}
        aria-label="Message"
        className="min-h-11 flex-1 rounded-full border border-line-strong bg-surface px-4 text-sm text-ink placeholder:text-faint"
      />
      <button type="submit" disabled={disabled || !text.trim()} aria-label="Send" className="grid size-11 place-items-center rounded-full bg-accent text-accent-contrast disabled:opacity-50">
        <SendHorizontal aria-hidden="true" className="size-5" />
      </button>
    </form>
  )
}

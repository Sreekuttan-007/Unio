import { Mic, Paperclip, SendHorizontal, Smile, Sparkles } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { cn } from './cn'

export interface ChatMessage {
  id: string
  from: 'user' | 'assistant'
  text: string
  time?: string
  /** Quick replies the assistant offers, such as a list of rooms. */
  choices?: string[]
  extra?: ReactNode
}

export function ChatThread({ messages, typing, onChoose }: { messages: ChatMessage[]; typing?: boolean; onChoose?: (choice: string) => void }) {
  return (
    <div className="space-y-4" role="log" aria-live="polite" aria-label="Conversation">
      {messages.map((message) => (
        <div key={message.id} className={cn('flex gap-2.5', message.from === 'user' && 'justify-end')}>
          {message.from === 'assistant' ? (
            <span aria-hidden="true" className="mt-1 grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-accent-ink shadow-xs">
              <Sparkles className="size-3.5" />
            </span>
          ) : null}
          <div className="max-w-[85%] space-y-2">
            <div
              className={cn(
                'rounded-2xl p-4 text-sm shadow-xs transition-colors',
                message.from === 'user'
                  ? 'bg-ink text-surface'
                  : 'border border-line/60 bg-surface text-ink',
              )}
            >
              <p className="leading-relaxed">{message.text}</p>
              <p className={cn('mt-1.5 text-right text-[0.6875rem]', message.from === 'user' ? 'text-surface/70' : 'text-faint')}>
                {message.time ?? '9:32'}
              </p>
            </div>
            {message.choices?.length ? (
              <div className="flex flex-wrap gap-2 pt-1">
                {message.choices.map((choice) => (
                  <button
                    key={choice}
                    type="button"
                    onClick={() => onChoose?.(choice)}
                    className="min-h-9 rounded-full border border-line bg-surface/90 px-3.5 text-xs font-medium text-ink shadow-xs transition-all hover:border-ink hover:bg-surface-2 active:scale-95"
                  >
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
        <p className="pl-9 text-xs font-medium text-muted" role="status">
          Thinking...
        </p>
      ) : null}
    </div>
  )
}

export function ChatComposer({
  onSend,
  disabled,
  placeholder = 'Write a message',
}: {
  onSend: (text: string) => void
  disabled?: boolean
  placeholder?: string
}) {
  const [text, setText] = useState('')
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!text.trim()) return
    onSend(text.trim())
    setText('')
  }
  return (
    <form onSubmit={submit} className="relative flex items-center">
      <input
        value={text}
        onChange={(event) => setText(event.target.value)}
        disabled={disabled}
        placeholder={placeholder}
        aria-label="Message"
        className="min-h-12 w-full rounded-full border border-line/80 bg-surface/95 py-2.5 pl-5 pr-28 text-sm text-ink placeholder:text-faint shadow-xs focus:border-ink focus:outline-none"
      />
      <div className="absolute right-2 flex items-center gap-1.5 text-muted">
        <button type="button" aria-label="Attach file" className="grid size-8 place-items-center rounded-full hover:bg-surface-2 hover:text-ink transition-colors">
          <Paperclip aria-hidden="true" className="size-4" />
        </button>
        <button type="button" aria-label="Emoji" className="grid size-8 place-items-center rounded-full hover:bg-surface-2 hover:text-ink transition-colors">
          <Smile aria-hidden="true" className="size-4" />
        </button>
        {text.trim() ? (
          <button
            type="submit"
            disabled={disabled}
            aria-label="Send"
            className="grid size-8 place-items-center rounded-full bg-ink text-surface transition-transform hover:opacity-90 active:scale-95"
          >
            <SendHorizontal aria-hidden="true" className="size-4" />
          </button>
        ) : (
          <button type="button" aria-label="Voice input" className="grid size-8 place-items-center rounded-full hover:bg-surface-2 hover:text-ink transition-colors">
            <Mic aria-hidden="true" className="size-4" />
          </button>
        )}
      </div>
    </form>
  )
}

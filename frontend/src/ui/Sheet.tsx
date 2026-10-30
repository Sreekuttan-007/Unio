import { X } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'

/** A panel for details: a bottom sheet on a phone, a right-hand drawer on a desktop. */
export function Sheet({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    closeRef.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-(--z-overlay)" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" aria-label="Close" tabIndex={-1} className="absolute inset-0 bg-ink/40" onClick={onClose} />
      <div className="absolute inset-x-0 bottom-0 flex max-h-[88dvh] flex-col rounded-t-lg border-t border-line bg-surface shadow-pop lg:inset-y-0 lg:left-auto lg:right-0 lg:max-h-none lg:w-[34rem] lg:rounded-none lg:border-l lg:border-t-0">
        <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
          <h2 className="min-w-0 truncate text-base font-semibold text-ink">{title}</h2>
          <button ref={closeRef} type="button" aria-label="Close" onClick={onClose} className="grid size-11 shrink-0 place-items-center rounded-full hover:bg-surface-2">
            <X aria-hidden="true" className="size-5" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4" style={{ paddingBottom: 'calc(1rem + env(safe-area-inset-bottom))' }}>
          {children}
        </div>
      </div>
    </div>
  )
}

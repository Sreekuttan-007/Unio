import { Camera, Upload } from 'lucide-react'
import { useId, useState, type DragEvent } from 'react'
import { cn } from './cn'

/**
 * A standard file input (what Median documents for camera and gallery in its WebView), plus real
 * drag-and-drop: drop a file anywhere on the zone and it's picked up the same way a click would.
 */
export function Dropzone({
  label,
  hint,
  accept,
  capture,
  onFiles,
}: {
  label: string
  hint?: string
  accept: string
  capture?: boolean
  onFiles: (files: File[]) => void
}) {
  const id = useId()
  const Icon = capture ? Camera : Upload
  const [dragging, setDragging] = useState(false)

  const onDragOver = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    if (event.dataTransfer.types.includes('Files')) setDragging(true)
  }
  const onDragLeave = (event: DragEvent<HTMLLabelElement>) => {
    // Only clear once the pointer actually leaves the zone, not when it crosses a child element.
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false)
  }
  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    setDragging(false)
    const files = Array.from(event.dataTransfer.files)
    if (files.length) onFiles(files)
  }

  return (
    <label
      htmlFor={id}
      onDragOver={onDragOver}
      onDragEnter={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={cn(
        'flex min-h-28 cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border-2 border-dashed px-4 py-6 text-center transition-colors',
        dragging ? 'border-accent bg-accent-soft' : 'border-line-strong bg-surface-2 hover:border-accent hover:bg-accent-soft',
      )}
    >
      <Icon aria-hidden="true" className="size-6 text-accent-ink" />
      <span className="text-sm font-medium text-ink">{dragging ? 'Drop it here' : label}</span>
      {hint ? <span className="text-xs text-muted">{hint}</span> : null}
      <input
        id={id}
        type="file"
        accept={accept}
        capture={capture ? 'environment' : undefined}
        className="sr-only"
        onChange={(event) => onFiles(Array.from(event.target.files ?? []))}
      />
    </label>
  )
}

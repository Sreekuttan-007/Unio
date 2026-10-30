import { Camera, Upload } from 'lucide-react'
import { useId } from 'react'

/**
 * A standard file input, which is what Median documents for camera and gallery in its WebView.
 * capture asks a phone for the camera directly.
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
  return (
    <label htmlFor={id} className="flex min-h-28 cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border-2 border-dashed border-line-strong bg-surface-2 px-4 py-6 text-center hover:border-accent hover:bg-accent-soft">
      <Icon aria-hidden="true" className="size-6 text-accent-ink" />
      <span className="text-sm font-medium text-ink">{label}</span>
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

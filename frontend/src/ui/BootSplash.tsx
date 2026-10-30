import { Brand } from './Brand'

export function BootSplash() {
  return (
    <div role="status" aria-label="Loading" className="grid min-h-dvh place-items-center">
      <div className="flex flex-col items-center gap-4">
        <Brand />
        <div aria-hidden="true" className="size-6 animate-spin rounded-full border-2 border-line-strong border-t-accent" />
      </div>
    </div>
  )
}

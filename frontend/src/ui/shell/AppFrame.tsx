import type { ReactNode } from 'react'

export interface AppFrameProps {
  topBar: ReactNode
  sideNav: ReactNode
  bottomNav: ReactNode
  children: ReactNode
}

const MAIN_STYLE = { paddingBottom: 'calc(var(--bottomnav-height) + env(safe-area-inset-bottom) + 1.5rem)' }

/** Desktop: sidebar plus content. Phone: content plus bottom bar. */
export function AppFrame({ topBar, sideNav, bottomNav, children }: AppFrameProps) {
  return (
    <div className="relative min-h-dvh overflow-x-clip bg-bg text-ink transition-colors">
      {/* Ambient background glows matching reference aesthetic */}
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
        <div className="absolute -left-20 -top-20 size-96 rounded-full bg-accent-soft/30 blur-3xl" />
        <div className="absolute -bottom-20 -left-10 size-80 rounded-full bg-lilac-soft/50 blur-3xl" />
        <div className="absolute right-0 top-1/4 size-96 rounded-full bg-surface-2/60 blur-3xl" />
      </div>
      <div className="relative z-10 flex min-h-dvh flex-col">
        {topBar}
        <div className="flex-1">
          {sideNav}
          <main id="main" tabIndex={-1} style={MAIN_STYLE} className="mx-auto w-full max-w-(--content-max) px-4 pt-6 outline-none lg:pl-28 lg:pr-8 lg:pb-12">
            {children}
          </main>
        </div>
        {bottomNav}
      </div>
    </div>
  )
}

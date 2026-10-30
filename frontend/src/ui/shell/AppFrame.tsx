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
    <div className="min-h-dvh bg-bg">
      {topBar}
      {sideNav}
      <main id="main" tabIndex={-1} style={MAIN_STYLE} className="mx-auto w-full max-w-(--content-max) px-4 pt-6 outline-none lg:pl-[calc(var(--nav-width)+2rem)] lg:pr-8 lg:pb-12">
        {children}
      </main>
      {bottomNav}
    </div>
  )
}

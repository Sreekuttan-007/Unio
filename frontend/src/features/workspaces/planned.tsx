import type { ComponentType } from 'react'
import { PlannedScreen, type PlannedScreenProps } from '@/ui'
import { SessionCard } from '../shell/SessionCard'

type PlannedMeta = PlannedScreenProps & {
  /** Show what the server decided about this session above the plan. Used on each role home. */
  session?: boolean
}

/** A screen a later phase builds. Each one states its phase and the requirements it serves. */
export function planned(meta: PlannedMeta): ComponentType {
  const { session, ...props } = meta
  function Planned() {
    return <PlannedScreen {...props}>{session ? <SessionCard /> : null}</PlannedScreen>
  }
  Planned.displayName = `Planned(${props.title})`
  return Planned
}

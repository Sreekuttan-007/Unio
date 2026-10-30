import { useEffect, useState } from 'react'
import { api } from './api/client'

const WAKING_AFTER_MS = 3_000
const COLD_START_TIMEOUT_MS = 65_000

/** Pings the backend once. A slow answer reads as "waking up", which a sleeping free host needs. */
export function useServerStatus(): { waking: boolean; reachable: boolean | null } {
  const [state, setState] = useState<{ waking: boolean; reachable: boolean | null }>({ waking: false, reachable: null })

  useEffect(() => {
    let finished = false
    const timer = setTimeout(() => {
      if (!finished) setState((current) => ({ ...current, waking: true }))
    }, WAKING_AFTER_MS)

    api('/system/ping', { auth: false, timeoutMs: COLD_START_TIMEOUT_MS })
      .then(() => {
        finished = true
        setState({ waking: false, reachable: true })
      })
      .catch(() => {
        finished = true
        setState({ waking: false, reachable: false })
      })

    return () => {
      finished = true
      clearTimeout(timer)
    }
  }, [])

  return state
}

import { describe, expect, it } from 'vitest'
import generated from '@/mocks/fixtures/generated.json'
import { SCREEN_REGISTRY } from './registry'

const bootstrap = generated.bootstrap as Record<string, { navigation: { key: string; path: string }[]; role: { workspace: string } }>
const serverKeys = new Set(Object.values(bootstrap).flatMap((role) => role.navigation.map((item) => item.key)))

describe('screen registry', () => {
  it('has a screen for every navigation key the backend can send', () => {
    const missing = [...serverKeys].filter((key) => !(key in SCREEN_REGISTRY))
    expect(missing).toEqual([])
  })

  it('has no screen the backend never sends (it would be dead code)', () => {
    const orphans = Object.keys(SCREEN_REGISTRY).filter((key) => !serverKeys.has(key))
    expect(orphans).toEqual([])
  })

  it('gives every role a distinct workspace and a path under it', () => {
    const workspaces = Object.values(bootstrap).map((role) => role.role.workspace)
    expect(new Set(workspaces).size).toBe(7)
    for (const role of Object.values(bootstrap)) {
      for (const item of role.navigation) expect(item.path.startsWith(`/w/${role.role.workspace}/`)).toBe(true)
    }
  })

  it('never shares a navigation key between two roles', () => {
    const all = Object.values(bootstrap).flatMap((role) => role.navigation.map((item) => item.key))
    expect(new Set(all).size).toBe(all.length)
  })
})

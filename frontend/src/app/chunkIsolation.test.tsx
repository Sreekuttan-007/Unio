import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { tokenStore } from '@/platform/auth/tokenStore'
import { AppRoutes } from './AppRoutes'
import { Providers } from './Providers'

// The factory runs only when something imports the procurement workspace, so the flag records
// whether a technician session ever pulled that code in.
const loaded = vi.hoisted(() => ({ procurement: false, system: false }))

vi.mock('@/features/workspaces/procurement', () => {
  loaded.procurement = true
  return { screens: {} }
})
vi.mock('@/features/workspaces/system', () => {
  loaded.system = true
  return { screens: {} }
})

describe('code splitting is the proof of per-role access', () => {
  it('never fetches the procurement or system screens for a technician, even when asked by URL', async () => {
    tokenStore.set('mock.TECHNICIAN')
    render(
      <Providers>
        <MemoryRouter initialEntries={['/w/procurement/queue']}>
          <AppRoutes />
        </MemoryRouter>
      </Providers>,
    )
    expect(await screen.findByText(/this is not part of your workspace/i)).toBeInTheDocument()
    expect(loaded.procurement).toBe(false)
    expect(loaded.system).toBe(false)
  })
})

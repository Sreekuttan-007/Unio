import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { createHandlers } from '@/mocks/handlers'
import { tokenStore } from '@/platform/auth/tokenStore'

export const server = setupServer(...createHandlers())

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))

afterEach(() => {
  cleanup()
  tokenStore.clear()
  window.localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
  document.documentElement.removeAttribute('data-accent')
  // Fresh handlers, so in-memory edits from one test never reach the next.
  server.resetHandlers(...createHandlers())
})

afterAll(() => server.close())

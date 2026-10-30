import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AppRoutes } from '@/app/AppRoutes'
import { Providers } from '@/app/Providers'
import '@/styles/index.css'

async function start() {
  // `npm run dev:mock` serves every endpoint from src/mocks, so the UI can be tuned with no backend.
  if (import.meta.env.VITE_USE_MOCKS === 'true') {
    const { worker } = await import('@/mocks/browser')
    await worker.start({ onUnhandledFrame: 'bypass' })
  }

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <Providers>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </Providers>
    </StrictMode>,
  )
}

void start()

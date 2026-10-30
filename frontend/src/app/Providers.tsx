import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { AuthProvider } from '@/platform/auth/AuthProvider'
import { AccentSync, ThemeProvider } from '@/platform/theme/ThemeProvider'

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { refetchOnWindowFocus: false, retry: 1 },
      mutations: { retry: 0 },
    },
  })
}

export function Providers({ children, client }: { children: ReactNode; client?: QueryClient }) {
  const [queryClient] = useState(() => client ?? createQueryClient())
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeProvider>
          <AccentSync />
          {children}
        </ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}

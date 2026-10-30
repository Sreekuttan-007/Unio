import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { api, ApiError, configureApi } from '../api/client'
import type { BootstrapResponse, TokenResponse } from '../api/types'
import { tokenStore } from './tokenStore'

/** offline: signed in locally, but the server could not be reached to confirm who you are. */
export type AuthStatus = 'booting' | 'signedOut' | 'signedIn' | 'offline'

interface AuthContextValue {
  status: AuthStatus
  bootstrap: BootstrapResponse | null
  retryBootstrap: () => void
  signInWithPassword: (email: string, password: string) => Promise<void>
  signInDemo: (email: string) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [token, setToken] = useState<string | null>(() => tokenStore.get())

  // Runs during render on purpose: it must be in place before any child query fires.
  useMemo(() => {
    configureApi({
      getToken: () => tokenStore.get(),
      onUnauthorized: () => {
        tokenStore.clear()
        queryClient.clear()
        setToken(null)
      },
    })
  }, [queryClient])

  const bootstrapQuery = useQuery({
    queryKey: ['bootstrap', token],
    queryFn: () => api<BootstrapResponse>('/me/bootstrap'),
    enabled: token !== null,
    staleTime: Infinity,
    retry: (count, error) => error instanceof ApiError && error.isNetwork && count < 2,
  })

  const adopt = useCallback(
    (response: TokenResponse) => {
      queryClient.clear()
      tokenStore.set(response.accessToken)
      setToken(response.accessToken)
    },
    [queryClient],
  )

  const value = useMemo<AuthContextValue>(() => {
    let status: AuthStatus
    if (token === null) status = 'signedOut'
    else if (bootstrapQuery.data) status = 'signedIn'
    else if (bootstrapQuery.error instanceof ApiError && bootstrapQuery.error.isNetwork) status = 'offline'
    else status = 'booting'

    return {
      status,
      bootstrap: bootstrapQuery.data ?? null,
      retryBootstrap: () => void bootstrapQuery.refetch(),
      signInWithPassword: async (email, password) => {
        adopt(await api<TokenResponse>('/auth/login', { method: 'POST', body: { email, password }, auth: false }))
      },
      signInDemo: async (email) => {
        adopt(await api<TokenResponse>('/auth/demo-login', { method: 'POST', body: { email }, auth: false }))
      },
      signOut: async () => {
        try {
          await api('/auth/logout', { method: 'POST' })
        } catch {
          // the token is dropped locally either way
        }
        tokenStore.clear()
        queryClient.clear()
        setToken(null)
      },
    }
  }, [token, bootstrapQuery.data, bootstrapQuery.error, bootstrapQuery.refetch, adopt, queryClient])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}

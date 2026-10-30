import type { ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { LoginScreen } from '@/features/auth/LoginScreen'
import { UiGallery } from '@/features/dev/UiGallery'
import { AppShell } from '@/features/shell/AppShell'
import { useAuth } from '@/platform/auth/AuthProvider'
import { WorkspaceRouter } from '@/platform/workspaces/WorkspaceRouter'
import { BootSplash, Button, NotPermitted, OfflineState } from '@/ui'

function RequireAuth({ children }: { children: ReactNode }) {
  const { status, retryBootstrap, signOut } = useAuth()
  const location = useLocation()

  if (status === 'booting') return <BootSplash />
  if (status === 'offline') {
    return (
      <div className="grid min-h-dvh place-items-center gap-4 p-4">
        <div className="space-y-4 text-center">
          <OfflineState onRetry={retryBootstrap} />
          <Button variant="ghost" onClick={() => void signOut()}>Sign out</Button>
        </div>
      </div>
    )
  }
  if (status === 'signedOut') return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <>{children}</>
}

function LoginRoute() {
  const { status, bootstrap } = useAuth()
  if (status === 'signedIn' && bootstrap) return <Navigate to={bootstrap.landingPath} replace />
  return <LoginScreen />
}

function RootRedirect() {
  const { status, bootstrap } = useAuth()
  if (status === 'booting') return <BootSplash />
  if (status === 'signedIn' && bootstrap) return <Navigate to={bootstrap.landingPath} replace />
  return <Navigate to="/login" replace />
}

function NotPermittedRoute() {
  const navigate = useNavigate()
  return (
    <div className="grid min-h-dvh place-items-center p-4">
      <NotPermitted onHome={() => navigate('/')} />
    </div>
  )
}

export function AppRoutes() {
  return (
    <Routes>
      {import.meta.env.DEV ? <Route path="/dev/ui" element={<UiGallery />} /> : null}
      <Route path="/login" element={<LoginRoute />} />
      <Route path="/not-permitted" element={<NotPermittedRoute />} />
      <Route
        path="/w/*"
        element={
          <RequireAuth>
            <AppShell>
              <WorkspaceRouter />
            </AppShell>
          </RequireAuth>
        }
      />
      <Route path="*" element={<RootRedirect />} />
    </Routes>
  )
}

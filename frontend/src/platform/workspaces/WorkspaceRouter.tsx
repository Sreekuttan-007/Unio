import { Suspense } from 'react'
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { NotPermitted, ScreenSkeleton } from '@/ui'
import { useAuth } from '../auth/AuthProvider'
import { ErrorBoundary } from '../ErrorBoundary'
import { SCREEN_REGISTRY } from './registry'

/** Navigation paths from the server are absolute (/w/technician/tasks). This router lives under /w/*. */
const relative = (path: string) => path.replace(/^\/w\//, '')

/**
 * Mounts exactly the routes the server put in this user navigation. Any other path, including a
 * valid screen of another role, falls through to NotPermitted without loading its code.
 */
export function WorkspaceRouter() {
  const { bootstrap } = useAuth()
  const navigate = useNavigate()
  if (!bootstrap) return null

  return (
    <ErrorBoundary>
      <Routes>
        <Route index element={<Navigate to={bootstrap.landingPath} replace />} />
        <Route path={bootstrap.role.workspace} element={<Navigate to={bootstrap.landingPath} replace />} />
        {bootstrap.navigation.map((item) => {
          const Screen = SCREEN_REGISTRY[item.key]
          if (!Screen) {
            console.warn(`No screen registered for navigation key ${item.key}`)
            return null
          }
          return (
            <Route
              key={item.key}
              path={relative(item.path)}
              element={
                <Suspense fallback={<ScreenSkeleton />}>
                  <Screen />
                </Suspense>
              }
            />
          )
        })}
        <Route path="*" element={<NotPermitted onHome={() => navigate(bootstrap.landingPath)} />} />
      </Routes>
    </ErrorBoundary>
  )
}

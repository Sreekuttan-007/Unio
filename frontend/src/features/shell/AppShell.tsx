import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api } from '@/platform/api/client'
import { useAuth } from '@/platform/auth/AuthProvider'
import { useTheme } from '@/platform/theme/ThemeProvider'
import { AppFrame, BottomNav, SideNav, TopBar, type NavEntryView } from '@/ui'
import { NotificationCentre } from './NotificationCentre'

const BADGE_POLL_MS = 15_000

/** Wires the presentation-only shell to the session. All role differences arrive as data. */
export function AppShell({ children }: { children: ReactNode }) {
  const { bootstrap, signOut } = useAuth()
  const { theme, setTheme } = useTheme()
  const { pathname } = useLocation()
  const navigate = useNavigate()

  const badges = useQuery({
    queryKey: ['badges'],
    queryFn: () => api<Record<string, number>>('/me/badges'),
    enabled: bootstrap !== null,
    refetchInterval: BADGE_POLL_MS,
  })

  if (!bootstrap) return null

  const items: NavEntryView[] = bootstrap.navigation.map((item) => ({
    key: item.key,
    label: item.label,
    path: item.path,
    icon: item.icon,
    badge: item.badge ? badges.data?.[item.badge.source] : undefined,
  }))

  const handleSignOut = () => {
    void signOut().then(() => navigate('/login', { replace: true }))
  }

  return (
    <AppFrame
      topBar={
        <TopBar
          roleLabel={bootstrap.role.label}
          userName={bootstrap.user.name}
          userEmail={bootstrap.user.email}
          initials={bootstrap.user.avatarInitials}
          theme={theme}
          onThemeChange={setTheme}
          onSignOut={handleSignOut}
          actions={<NotificationCentre unread={badges.data?.['notifications.unread'] ?? 0} />}
        />
      }
      sideNav={<SideNav items={items} activePath={pathname} roleLabel={bootstrap.role.label} onNavigate={navigate} />}
      bottomNav={<BottomNav items={items} activePath={pathname} onNavigate={navigate} />}
    >
      {children}
    </AppFrame>
  )
}

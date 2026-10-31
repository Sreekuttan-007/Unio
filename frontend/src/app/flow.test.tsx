import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import generated from '@/mocks/fixtures/generated.json'
import { tokenStore } from '@/platform/auth/tokenStore'
import { AppRoutes } from './AppRoutes'
import { Providers } from './Providers'

type Fixture = { navigation: { key: string; label: string }[]; user: { name: string }; theme: { accent: string }; role: { workspace: string } }
const bootstrap = generated.bootstrap as unknown as Record<string, Fixture>
const accounts = generated.demoAccounts as { email: string; roleKey: string }[]

function renderApp(path: string) {
  return render(
    <Providers>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </Providers>,
  )
}

const navKeys = () => screen.queryAllByTestId(/^nav-/).map((node) => node.dataset.testid!.replace('nav-', ''))

describe('landing page', () => {
  it('renders the cinematic landing page with hero, navigation and CTAs', async () => {
    renderApp('/')
    expect(await screen.findByRole('heading', { level: 1, name: /One Campus/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Get Started/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Explore UNIO/i })).toBeInTheDocument()
  })
})

describe('signing in', () => {
  it('sends a visitor to the login screen with one demo chip per role', async () => {
    renderApp('/login')
    expect(await screen.findByRole('heading', { name: /welcome back/i })).toBeInTheDocument()
    expect(await screen.findAllByTestId(/^demo-/)).toHaveLength(7)
  })

  it.each(accounts.map((account) => [account.roleKey, account.email]))(
    '%s lands on its own workspace and sees only its own navigation',
    async (roleKey, email) => {
      const expected = bootstrap[roleKey!]!
      renderApp('/login')
      await userEvent.click(await screen.findByTestId(`demo-${email}`))

      expect(await screen.findByRole('heading', { level: 1, name: expected.navigation[0]!.label })).toBeInTheDocument()
      expect(navKeys()).toEqual(expected.navigation.map((item) => item.key))
      expect(document.documentElement.dataset.accent).toBe(expected.theme.accent)
      for (const key of navKeys()) expect(key.split('.')[0]).toBe(navKeys()[0]!.split('.')[0])
    },
  )

  it('shows an error for a wrong password and stays on the login screen', async () => {
    renderApp('/login')
    await userEvent.type(await screen.findByLabelText('Email'), 'tech@unio.demo')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong-password')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByTestId('login-error')).toHaveTextContent('Incorrect email or password.')
    expect(tokenStore.get()).toBeNull()
  })

  it('signs in with a password', async () => {
    renderApp('/login')
    await userEvent.type(await screen.findByLabelText('Email'), 'student@unio.demo')
    await userEvent.type(screen.getByLabelText('Password'), 'Unio@Demo2026')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Home' })).toBeInTheDocument()
  })
})

describe('one workspace per role', () => {
  it('refuses a screen from another role and says so, inside the shell', async () => {
    tokenStore.set('mock.TECHNICIAN')
    renderApp('/w/procurement/queue')
    expect(await screen.findByText(/this is not part of your workspace/i)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Approval Queue' })).not.toBeInTheDocument()
    expect(navKeys()).toEqual(bootstrap.TECHNICIAN!.navigation.map((item) => item.key))
  })

  it('opens a permitted screen directly by URL', async () => {
    tokenStore.set('mock.TECHNICIAN')
    renderApp('/w/technician/parts')
    expect(await screen.findByRole('heading', { level: 1, name: 'Parts' })).toBeInTheDocument()
    expect(screen.getByTestId('nav-tech.parts')).toHaveAttribute('aria-current', 'page')
  })

  it('moves between screens from the sidebar', async () => {
    tokenStore.set('mock.TECHNICIAN')
    renderApp('/w/technician/tasks')
    await screen.findByRole('heading', { level: 1, name: 'My Tasks' })
    await userEvent.click(screen.getByTestId('nav-tech.availability'))
    expect(await screen.findByRole('heading', { level: 1, name: 'Availability' })).toBeInTheDocument()
  })

  it('shows what the server decided about this session on the role home', async () => {
    tokenStore.set('mock.TECHNICIAN')
    renderApp('/w/technician/tasks')
    const card = await screen.findByTestId('session-card')
    expect(within(card).getByText('Ravi Kumar')).toBeInTheDocument()
    expect(within(card).getByText(/work order: assigned/i)).toBeInTheDocument()
  })

  it('drops back to the login screen when the server rejects the token', async () => {
    tokenStore.set('mock.SOMEONE_ELSE')
    renderApp('/w/student/home')
    expect(await screen.findByRole('heading', { name: /welcome back/i })).toBeInTheDocument()
    expect(tokenStore.get()).toBeNull()
  })

  it('signs out and clears the session', async () => {
    tokenStore.set('mock.STUDENT')
    renderApp('/w/student/home')
    await screen.findByRole('heading', { level: 1, name: 'Home' })
    await userEvent.click(screen.getByTestId('account-menu'))
    await userEvent.click(screen.getByTestId('sign-out'))
    expect(await screen.findByRole('heading', { name: /welcome back/i })).toBeInTheDocument()
    await waitFor(() => expect(tokenStore.get()).toBeNull())
  })
})

describe('system administration screens', () => {
  it('lists users and offers only the actions the server allows', async () => {
    tokenStore.set('mock.SYSTEM_ADMIN')
    renderApp('/w/system/users')
    await screen.findByRole('heading', { level: 1, name: 'Users' })

    const self = (await screen.findByText('Sam Thomas')).closest('tr')!
    expect(within(self).queryByRole('button', { name: 'Deactivate' })).not.toBeInTheDocument()
    expect(within(self).getByText('You cannot deactivate your own account.')).toBeInTheDocument()

    const other = screen.getByText('Ravi Kumar').closest('tr')!
    await userEvent.click(within(other).getByRole('button', { name: 'Deactivate' }))
    await waitFor(() => expect(within(screen.getByText('Ravi Kumar').closest('tr')!).getByText('Inactive')).toBeInTheDocument())
  })

  it('edits a role and confirms the change', async () => {
    tokenStore.set('mock.SYSTEM_ADMIN')
    renderApp('/w/system/roles')
    await screen.findByRole('heading', { level: 1, name: 'Roles & Permissions' })
    await userEvent.click(await screen.findByRole('button', { name: /^Technician/ }))

    const save = screen.getByRole('button', { name: 'Save changes' })
    expect(save).toBeDisabled()
    await userEvent.click(screen.getByRole('checkbox', { name: 'inventory.read.reserved' }))
    expect(save).toBeEnabled()
    await userEvent.click(save)
    expect(await screen.findByTestId('roles-message')).toHaveTextContent('Technician updated')
  })

  it('shows the audit log', async () => {
    tokenStore.set('mock.SYSTEM_ADMIN')
    renderApp('/w/system/audit')
    expect(await screen.findByRole('heading', { level: 1, name: 'Audit Logs' })).toBeInTheDocument()
    expect(await screen.findByText('role.permissions.update')).toBeInTheDocument()
  })
})

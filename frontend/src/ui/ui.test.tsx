import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { BottomNav, Dropzone, LoginCard, NavIcon, SideNav, KNOWN_ICON_NAMES, type NavEntryView } from '@/ui'

const accounts = [
  { email: 'tech@unio.demo', name: 'Ravi Kumar', roleLabel: 'Technician', accent: 'amber' },
  { email: 'student@unio.demo', name: 'Asha Nair', roleLabel: 'Student', accent: 'sky' },
]

const baseLogin = { demoAccounts: accounts, busyEmail: null, submitting: false, error: null, waking: false, onDemoLogin: vi.fn(), onSubmit: vi.fn() }

describe('LoginCard', () => {
  it('lets a demo role be tapped, and carries that role accent on its chip', async () => {
    const onDemoLogin = vi.fn()
    render(<LoginCard {...baseLogin} onDemoLogin={onDemoLogin} />)
    const chip = screen.getByTestId('demo-tech@unio.demo')
    expect(chip).toHaveAttribute('data-accent', 'amber')
    await userEvent.click(chip)
    expect(onDemoLogin).toHaveBeenCalledWith('tech@unio.demo')
  })

  it('keeps Sign in disabled until both fields are filled, then submits them', async () => {
    const onSubmit = vi.fn()
    render(<LoginCard {...baseLogin} onSubmit={onSubmit} />)
    const submit = screen.getByRole('button', { name: 'Sign in' })
    expect(submit).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Email'), 'a@b.co')
    expect(submit).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Password'), 'secret')
    expect(submit).toBeEnabled()
    await userEvent.click(submit)
    expect(onSubmit).toHaveBeenCalledWith('a@b.co', 'secret')
  })

  it('disables every action while one sign-in is running', () => {
    render(<LoginCard {...baseLogin} busyEmail="tech@unio.demo" />)
    expect(screen.getByTestId('demo-tech@unio.demo')).toBeDisabled()
    expect(screen.getByTestId('demo-student@unio.demo')).toBeDisabled()
  })

  it('shows an error as an alert, and the waking notice as a status', () => {
    render(<LoginCard {...baseLogin} error="Incorrect email or password." waking />)
    expect(screen.getByRole('alert')).toHaveTextContent('Incorrect email or password.')
    expect(screen.getByRole('status')).toHaveTextContent(/waking the server/i)
  })

  it('shows no demo section when the server offers none', () => {
    render(<LoginCard {...baseLogin} demoAccounts={[]} />)
    expect(screen.queryByText(/tap a role/i)).not.toBeInTheDocument()
  })
})

const items = (count: number): NavEntryView[] =>
  Array.from({ length: count }, (_, index) => ({ key: `k.${index}`, label: `Item ${index}`, path: `/w/x/${index}`, icon: 'house' }))

describe('BottomNav', () => {
  it('puts up to five items on the bar with no More button', () => {
    render(<BottomNav items={items(5)} activePath="/w/x/0" onNavigate={vi.fn()} />)
    expect(screen.getAllByRole('button')).toHaveLength(5)
    expect(screen.queryByRole('button', { name: 'More' })).not.toBeInTheDocument()
  })

  it('moves the rest under More when there are too many, and navigates from the sheet', async () => {
    const onNavigate = vi.fn()
    render(<BottomNav items={items(9)} activePath="/w/x/0" onNavigate={onNavigate} />)
    expect(screen.getAllByRole('button')).toHaveLength(5)
    expect(screen.queryByText('Item 8')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'More' }))
    const sheet = screen.getByRole('dialog', { name: 'More screens' })
    expect(within(sheet).getAllByRole('button', { name: /Item/ })).toHaveLength(5)
    await userEvent.click(within(sheet).getByRole('button', { name: 'Item 8' }))
    expect(onNavigate).toHaveBeenCalledWith('/w/x/8')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('marks the current screen', () => {
    render(<BottomNav items={items(3)} activePath="/w/x/1/detail" onNavigate={vi.fn()} />)
    expect(screen.getByTestId('bottomnav-k.1')).toHaveAttribute('aria-current', 'page')
    expect(screen.getByTestId('bottomnav-k.0')).not.toHaveAttribute('aria-current')
  })
})

describe('SideNav', () => {
  it('renders only the items it is given, with no role logic of its own', () => {
    render(<SideNav items={items(2)} activePath="/w/x/0" roleLabel="Anyone" onNavigate={vi.fn()} />)
    expect(screen.getAllByRole('link')).toHaveLength(2)
  })

  it('navigates without a full page load', async () => {
    const onNavigate = vi.fn()
    render(<SideNav items={items(2)} activePath="/w/x/0" roleLabel="Anyone" onNavigate={onNavigate} />)
    await userEvent.click(screen.getByRole('link', { name: 'Item 1' }))
    expect(onNavigate).toHaveBeenCalledWith('/w/x/1')
  })

  it('shows a badge only when the count is above zero', () => {
    const withBadge: NavEntryView[] = [{ ...items(1)[0]!, badge: 4 }, { ...items(2)[1]!, badge: 0 }]
    render(<SideNav items={withBadge} activePath="/" roleLabel="Anyone" onNavigate={vi.fn()} />)
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })
})

describe('NavIcon', () => {
  it('has an icon for every name the backend uses', async () => {
    const { default: generated } = await import('@/mocks/fixtures/generated.json')
    const used = new Set(Object.values(generated.bootstrap).flatMap((role) => role.navigation.map((item) => item.icon)))
    const unknown = [...used].filter((name) => !KNOWN_ICON_NAMES.includes(name))
    expect(unknown).toEqual([])
  })

  it('falls back instead of crashing on an unknown name', () => {
    const { container } = render(<NavIcon name="not-a-real-icon" />)
    expect(container.querySelector('svg')).toBeInTheDocument()
  })
})

describe('Dropzone', () => {
  const dataTransfer = (files: File[]) => ({ types: ['Files'], files, items: files.map((file) => ({ kind: 'file', type: file.type, getAsFile: () => file })) })

  it('accepts a file picked through the input, same as before', async () => {
    const onFiles = vi.fn()
    render(<Dropzone label="Add a photo" accept="image/*" onFiles={onFiles} />)
    const file = new File(['x'], 'photo.jpg', { type: 'image/jpeg' })
    await userEvent.upload(screen.getByLabelText('Add a photo'), file)
    expect(onFiles).toHaveBeenCalledWith([file])
  })

  it('shows drop feedback while a file is dragged over it, and accepts a dropped file', () => {
    const onFiles = vi.fn()
    render(<Dropzone label="Add a photo" accept="image/*" onFiles={onFiles} />)
    // The drag handlers live on the visible <label>, not the sr-only <input> getByLabelText resolves to.
    const zone = screen.getByText('Add a photo').closest('label')!
    const file = new File(['x'], 'photo.jpg', { type: 'image/jpeg' })

    fireEvent.dragEnter(zone, { dataTransfer: dataTransfer([file]) })
    expect(screen.getByText('Drop it here')).toBeInTheDocument()

    fireEvent.drop(zone, { dataTransfer: dataTransfer([file]) })
    expect(onFiles).toHaveBeenCalledWith([file])
    expect(screen.queryByText('Drop it here')).not.toBeInTheDocument()
  })

  it('does not call onFiles for a drag that leaves without dropping', () => {
    const onFiles = vi.fn()
    render(<Dropzone label="Add a photo" accept="image/*" onFiles={onFiles} />)
    const zone = screen.getByText('Add a photo').closest('label')!
    fireEvent.dragEnter(zone, { dataTransfer: dataTransfer([new File(['x'], 'photo.jpg')]) })
    fireEvent.dragLeave(zone, { relatedTarget: document.body })
    expect(screen.queryByText('Drop it here')).not.toBeInTheDocument()
    expect(onFiles).not.toHaveBeenCalled()
  })
})

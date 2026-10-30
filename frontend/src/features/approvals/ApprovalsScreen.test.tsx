import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { Providers } from '@/app/Providers'
import { AppRoutes } from '@/app/AppRoutes'
import { tokenStore } from '@/platform/auth/tokenStore'

function renderApp(path: string) {
  return render(
    <Providers>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </Providers>,
  )
}

describe('answering a clarification question', () => {
  it('asks, then lets only the requester answer, and the request goes back to a decider', async () => {
    const user = userEvent.setup()

    // A Facilities Administrator (a decider for PURCHASE) asks a question.
    tokenStore.set('mock.FACILITIES_ADMIN')
    const asker = renderApp('/w/facilities/approvals')
    await user.click(await screen.findByTestId('approval-APR-610'))
    await user.type(await screen.findByLabelText('Reason (kept in the audit trail)'), 'Which supplier should this go to?')
    await user.click(screen.getByRole('button', { name: 'Ask for clarification' }))
    // Asking closes the sheet (same as any other decision); confirm it from the list row's new status.
    expect(await within(await screen.findByTestId('approval-APR-610')).findByText('Needs clarification')).toBeInTheDocument()
    asker.unmount()

    // The requester (Meera Iyer, Department Manager) sees the question and answers it.
    tokenStore.set('mock.DEPARTMENT_MANAGER')
    const requester = renderApp('/w/department/approvals')
    await user.click(await screen.findByTestId('approval-APR-610'))
    expect(await screen.findByText('They asked a question')).toBeInTheDocument()
    expect((await screen.findAllByText('Which supplier should this go to?')).length).toBeGreaterThan(0)
    // The requester never sees decide buttons for their own request.
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('Your answer'), 'Brightline Electricals, same as last time.')
    await user.click(screen.getByRole('button', { name: 'Send answer' }))
    requester.unmount()

    // Back with a decider: the question is answered and it is waiting for a decision again.
    tokenStore.set('mock.FACILITIES_ADMIN')
    renderApp('/w/facilities/approvals')
    await user.click(await screen.findByTestId('approval-APR-610'))
    expect(await screen.findByText('Brightline Electricals, same as last time.')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'Approve' })).toBeInTheDocument()
  })
})

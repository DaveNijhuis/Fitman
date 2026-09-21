import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import WorkoutDetailPage from '../WorkoutDetailPage'
import * as sessions from '../../api/workoutSessions'

/**
 * Deleting a finished workout from its detail page (#336). It takes a
 * deliberate tap and a confirmation naming the workout, and can't be undone;
 * afterwards History no longer lists it.
 */

const SUMMARY = {
  id: 42, session: 'Push A', started_at: '2026-09-21T08:00:00Z', ended_at: '2026-09-21T09:00:00Z',
  volume_kg: 1234, set_count: 12,
}

function renderAt() {
  render(
    <MemoryRouter initialEntries={[{ pathname: '/history/42', state: SUMMARY }]}>
      <Routes>
        <Route path="/history/:sessionId" element={<WorkoutDetailPage />} />
        <Route path="/history" element={<div>History list</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.spyOn(sessions, 'getSessionLogs').mockResolvedValue([])
  vi.spyOn(sessions, 'deleteSession').mockResolvedValue(undefined)
})

afterEach(() => { vi.restoreAllMocks() })

describe('deleting a finished workout', () => {
  it('asks first, naming the workout and its date', async () => {
    renderAt()
    fireEvent.click(await screen.findByRole('button', { name: /delete workout/i }))
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent('Push A')
    expect(dialog).toHaveTextContent(/21 September/)
    expect(dialog).toHaveTextContent(/can.t be undone/i)
    expect(sessions.deleteSession).not.toHaveBeenCalled()
  })

  it('keeps the workout when cancelled', async () => {
    renderAt()
    fireEvent.click(await screen.findByRole('button', { name: /delete workout/i }))
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(sessions.deleteSession).not.toHaveBeenCalled()
  })

  it('deletes it and goes back to History when confirmed', async () => {
    renderAt()
    fireEvent.click(await screen.findByRole('button', { name: /delete workout/i }))
    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }))
    await waitFor(() => expect(sessions.deleteSession).toHaveBeenCalledWith(42))
    expect(await screen.findByText('History list')).toBeInTheDocument()
  })

  it('shows the error and stays when the delete fails', async () => {
    vi.mocked(sessions.deleteSession).mockRejectedValue(new Error('Session not found'))
    renderAt()
    fireEvent.click(await screen.findByRole('button', { name: /delete workout/i }))
    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Session not found')
    expect(screen.queryByText('History list')).toBeNull()
  })

  it('still offers it when opened by URL, without the summary', async () => {
    render(
      <MemoryRouter initialEntries={['/history/42']}>
        <Routes><Route path="/history/:sessionId" element={<WorkoutDetailPage />} /></Routes>
      </MemoryRouter>,
    )
    fireEvent.click(await screen.findByRole('button', { name: /delete workout/i }))
    expect(screen.getByRole('dialog')).toHaveTextContent(/this workout/i)
  })
})

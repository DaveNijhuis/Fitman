import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ActiveWorkoutPage from '../ActiveWorkoutPage'
import * as sessions from '../../api/workoutSessions'
import * as templates from '../../api/templates'
import * as logs from '../../api/logs'

/**
 * A finished workout stays finished (#338). The in-progress marker in browser
 * storage could outlive the workout: finishing ended the session on the
 * server first and cleared the marker second, so leaving the page in between
 * kept "Resume Push A" on offer for a workout already in History. Resuming it
 * let sets be added to the finished workout.
 */

const STARTED = '2026-09-21T08:00:00Z'
const EXERCISE = { id: 5, name: 'Bench Press', muscles: 'Chest', type: 'weight', equip: 'Barbell' }
const TEMPLATE = { id: 7, name: 'Push A', focus: null, colour: null, builtin: true, exercises: [EXERCISE] }

function renderAt(state: unknown = { session: 'Push A' }) {
  render(
    <MemoryRouter initialEntries={[{ pathname: '/workout/42', state }]}>
      <Routes>
        <Route path="/workout/:sessionId" element={<ActiveWorkoutPage />} />
        <Route path="/history/:sessionId" element={<div>History entry</div>} />
        <Route path="/" element={<div>Home</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  sessions.saveActiveWorkout(42, 'Push A', STARTED)
  vi.spyOn(sessions, 'getSession').mockResolvedValue({ id: 42, session: 'Push A', template_id: 7, started_at: STARTED, ended_at: null })
  vi.spyOn(sessions, 'getSessionLogs').mockResolvedValue([])
  vi.spyOn(templates, 'getTemplate').mockResolvedValue(TEMPLATE)
  vi.spyOn(logs, 'getLastSet').mockResolvedValue({ id: 1, exercise_id: 5, session_id: 1, weight: 60, reps: 8, logged_at: STARTED })
})

afterEach(() => {
  vi.restoreAllMocks()
  sessions.clearActiveWorkout()
})

/**
 * The workout's exercises come from its template on the server (#355), not
 * from a session name in navigation state — which a reload or a bookmarked
 * URL doesn't carry, so the page used to bounce home.
 */
describe('loading the workout', () => {
  it("loads the exercises of the workout's template", async () => {
    renderAt()
    expect(await screen.findByText('Bench Press')).toBeInTheDocument()
    expect(templates.getTemplate).toHaveBeenCalledWith(7)
  })

  it('opens without navigation state, as after a reload', async () => {
    renderAt(null)
    expect(await screen.findByText('Bench Press')).toBeInTheDocument()
    expect(screen.queryByText('Home')).toBeNull()
  })
})

describe('opening a workout that is no longer in progress', () => {
  it('keeps an in-progress workout open', async () => {
    renderAt()
    expect(await screen.findByText('Bench Press')).toBeInTheDocument()
    expect(sessions.getActiveWorkout()?.id).toBe(42)
  })

  it('goes to the History entry of a finished workout and stops offering Resume', async () => {
    vi.mocked(sessions.getSession).mockResolvedValue({ id: 42, session: 'Push A', template_id: 7, started_at: STARTED, ended_at: '2026-09-21T09:00:00Z' })
    renderAt()
    expect(await screen.findByText('History entry')).toBeInTheDocument()
    expect(sessions.getActiveWorkout()).toBeNull()
  })

  it('goes home when the workout no longer exists', async () => {
    vi.mocked(sessions.getSession).mockRejectedValue(new Error('Session not found'))
    renderAt()
    expect(await screen.findByText('Home')).toBeInTheDocument()
    expect(sessions.getActiveWorkout()).toBeNull()
  })

  it('leaves the marker alone when it belongs to another workout', async () => {
    sessions.saveActiveWorkout(43, 'Pull A', STARTED)
    vi.mocked(sessions.getSession).mockResolvedValue({ id: 42, session: 'Push A', template_id: 7, started_at: STARTED, ended_at: '2026-09-21T09:00:00Z' })
    renderAt()
    expect(await screen.findByText('History entry')).toBeInTheDocument()
    expect(sessions.getActiveWorkout()?.id).toBe(43)
  })

  it('keeps the marker when the check merely fails, e.g. offline', async () => {
    vi.mocked(sessions.getSession).mockRejectedValue(new Error('Failed to fetch'))
    renderAt()
    // Exercises come from the workout's template since #355, so with the
    // workout unreadable there are none to show; what matters is staying put.
    await waitFor(() => expect(sessions.getSession).toHaveBeenCalled())
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(screen.queryByText('Home')).toBeNull()
    expect(screen.queryByText('History entry')).toBeNull()
    expect(sessions.getActiveWorkout()?.id).toBe(42)
  })

  it('goes to History when a set is refused because the workout ended elsewhere', async () => {
    vi.spyOn(logs, 'logSet').mockRejectedValue(new Error('Session already ended'))
    renderAt()
    await screen.findByText('Bench Press')
    fireEvent.click(screen.getByRole('button', { name: 'Log Bench Press set 1' }))
    expect(await screen.findByText('History entry')).toBeInTheDocument()
    expect(sessions.getActiveWorkout()).toBeNull()
  })
})

describe('finishing', () => {
  function finish() {
    fireEvent.click(screen.getByRole('button', { name: /finish workout/i }))
    fireEvent.click(screen.getByRole('button', { name: /save & finish/i }))
  }

  it('clears the marker before the server ends the session', async () => {
    let markerWhileEnding: unknown = 'not called'
    vi.spyOn(sessions, 'endSession').mockImplementation(async () => {
      markerWhileEnding = sessions.getActiveWorkout()
      return { id: 42, session: 'Push A', template_id: 7, started_at: STARTED, ended_at: '2026-09-21T09:00:00Z' }
    })
    renderAt()
    await screen.findByText('Bench Press')
    finish()
    expect(await screen.findByText('Home')).toBeInTheDocument()
    expect(markerWhileEnding).toBeNull()
  })

  it('puts the marker back if the server could not end it', async () => {
    vi.spyOn(sessions, 'endSession').mockRejectedValue(new Error('Failed to fetch'))
    renderAt()
    await screen.findByText('Bench Press')
    finish()
    await waitFor(() => expect(sessions.endSession).toHaveBeenCalled())
    await waitFor(() => expect(sessions.getActiveWorkout()).toEqual({ id: 42, session: 'Push A', startedAt: STARTED }))
    expect(screen.queryByText('Home')).toBeNull()
    expect(await screen.findByText(/workout not finished/i)).toBeInTheDocument()
  })

  it('goes to History if it was already finished elsewhere', async () => {
    vi.spyOn(sessions, 'endSession').mockRejectedValue(new Error('Session already ended'))
    renderAt()
    await screen.findByText('Bench Press')
    finish()
    expect(await screen.findByText('History entry')).toBeInTheDocument()
    expect(sessions.getActiveWorkout()).toBeNull()
  })
})

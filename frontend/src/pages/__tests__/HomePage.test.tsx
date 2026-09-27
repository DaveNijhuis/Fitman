import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import HomePage from '../HomePage'
import * as templates from '../../api/templates'
import * as sessions from '../../api/workoutSessions'
import * as stats from '../../api/stats'

/**
 * Quick start lists the templates the server returns (#355). The names,
 * focus lines and colours used to be hard-coded for Push/Pull/Legs A, so a
 * template the code had never heard of showed with no focus line at all.
 */

const TEMPLATES = [
  { id: 1, name: 'Push A', focus: 'Chest · Shoulders · Triceps', colour: '#ff5a36', builtin: true },
  { id: 9, name: 'Chest Day', focus: 'Chest · Upper Chest', colour: '#123456', builtin: false },
]

function renderHome() {
  render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/workout/:sessionId" element={<div>Workout page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.spyOn(templates, 'getTemplates').mockResolvedValue(TEMPLATES)
  vi.spyOn(stats, 'getHomeStats').mockResolvedValue({
    streak: 0, week_workouts: 0, week_volume: 0, week_minutes: 0, prev_week_volume: 0,
  })
  vi.spyOn(sessions, 'startSession').mockResolvedValue({
    id: 77, session: 'Chest Day', template_id: 9, started_at: '2026-09-27T08:00:00Z', ended_at: null,
  })
})

afterEach(() => {
  vi.restoreAllMocks()
  sessions.clearActiveWorkout()
})

describe('quick start', () => {
  it('lists every template from the server, with its own focus line', async () => {
    renderHome()
    expect(await screen.findByText('Chest Day')).toBeInTheDocument()
    expect(screen.getByText('Chest · Upper Chest')).toBeInTheDocument()
    expect(screen.getByText('Push A')).toBeInTheDocument()
    expect(screen.getByText('Chest · Shoulders · Triceps')).toBeInTheDocument()
  })

  it('starts a workout by template id and remembers it as in progress', async () => {
    renderHome()
    fireEvent.click(await screen.findByText('Chest Day'))
    expect(await screen.findByText('Workout page')).toBeInTheDocument()
    expect(sessions.startSession).toHaveBeenCalledWith(9)
    expect(sessions.getActiveWorkout()).toMatchObject({ id: 77, session: 'Chest Day' })
  })
})

import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import SessionPickerSheet from '../SessionPickerSheet'
import * as templates from '../../api/templates'
import * as sessions from '../../api/workoutSessions'

/** The + button's picker lists the server's templates, like Quick start (#355). */

const TEMPLATES = [
  { id: 3, name: 'Legs A', focus: 'Quads · Glutes · Hamstrings', colour: '#1f9d62', builtin: true, hidden: false },
  { id: 9, name: 'Chest Day', focus: 'Chest · Upper Chest', colour: '#123456', builtin: false, hidden: false },
  { id: 4, name: 'Push B', focus: 'Shoulders · Chest · Triceps', colour: '#ff5a36', builtin: true, hidden: true },
]

function renderPicker(onClose = vi.fn()) {
  render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<SessionPickerSheet onClose={onClose} />} />
        <Route path="/workout/:sessionId" element={<div>Workout page</div>} />
      </Routes>
    </MemoryRouter>,
  )
  return onClose
}

beforeEach(() => {
  vi.spyOn(templates, 'getTemplates').mockResolvedValue(TEMPLATES)
  vi.spyOn(sessions, 'startSession').mockResolvedValue({
    id: 78, session: 'Chest Day', template_id: 9, started_at: '2026-09-27T08:00:00Z', ended_at: null,
  })
})

afterEach(() => {
  vi.restoreAllMocks()
  sessions.clearActiveWorkout()
})

describe('session picker', () => {
  it('lists every template from the server, with its own focus line', async () => {
    renderPicker()
    expect(await screen.findByText('Chest Day')).toBeInTheDocument()
    expect(screen.getByText('Chest · Upper Chest')).toBeInTheDocument()
    expect(screen.getByText('Quads · Glutes · Hamstrings')).toBeInTheDocument()
  })

  it('starts a workout by template id, closes, and opens it', async () => {
    const onClose = renderPicker()
    fireEvent.click(await screen.findByText('Chest Day'))
    expect(await screen.findByText('Workout page')).toBeInTheDocument()
    expect(sessions.startSession).toHaveBeenCalledWith(9)
    expect(onClose).toHaveBeenCalled()
    expect(sessions.getActiveWorkout()).toMatchObject({ id: 78, session: 'Chest Day' })
  })

  it('leaves out the built-ins you have hidden (#359)', async () => {
    renderPicker()
    await screen.findByText('Chest Day')
    expect(screen.queryByText('Push B')).toBeNull()
  })
})

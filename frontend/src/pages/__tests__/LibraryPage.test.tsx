import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import LibraryPage from '../LibraryPage'
import * as templates from '../../api/templates'
import * as exercises from '../../api/exercises'

/**
 * The Library filters by template (#355). Its tabs were a hard-coded list of
 * three session names; an exercise now sits in any number of templates, and
 * a template the code has never seen gets a tab too.
 */

const TEMPLATES = [
  { id: 1, name: 'Push A', focus: null, colour: '#ff5a36', builtin: true },
  { id: 9, name: 'Chest Day', focus: null, colour: '#123456', builtin: false },
]
const BENCH = { id: 5, name: 'Flat DB Bench Press', muscles: 'Chest', type: 'weight', equip: 'Dumbbell' }

beforeEach(() => {
  vi.spyOn(templates, 'getTemplates').mockResolvedValue(TEMPLATES)
  vi.spyOn(exercises, 'getAllExercises').mockResolvedValue([BENCH])
})

afterEach(() => { vi.restoreAllMocks() })

describe('library tabs', () => {
  it('offers All plus a tab per template from the server', async () => {
    render(<MemoryRouter><LibraryPage /></MemoryRouter>)
    expect(await screen.findByRole('button', { name: 'Chest Day' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Push A' })).toBeInTheDocument()
  })

  it('starts on All, which asks for the whole library', async () => {
    render(<MemoryRouter><LibraryPage /></MemoryRouter>)
    expect(await screen.findByText('Flat DB Bench Press')).toBeInTheDocument()
    expect(exercises.getAllExercises).toHaveBeenLastCalledWith(undefined, undefined)
  })

  it('filters by the chosen template id', async () => {
    render(<MemoryRouter><LibraryPage /></MemoryRouter>)
    fireEvent.click(await screen.findByRole('button', { name: 'Chest Day' }))
    await waitFor(() => expect(exercises.getAllExercises).toHaveBeenLastCalledWith(9, undefined))
  })
})

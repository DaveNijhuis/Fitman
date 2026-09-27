import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
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
const BENCH = {
  id: 5, name: 'Flat DB Bench Press', muscles: 'Chest', type: 'weight', equip: 'Dumbbell',
  custom: false, archived: false,
}
const FLY = {
  id: 60, name: 'Cable Fly', muscles: 'Chest', type: 'weight', equip: 'Cable',
  custom: true, archived: false,
}

function renderLibrary() {
  render(<MemoryRouter><LibraryPage /></MemoryRouter>)
}

beforeEach(() => {
  vi.spyOn(templates, 'getTemplates').mockResolvedValue(TEMPLATES)
  vi.spyOn(exercises, 'getAllExercises').mockResolvedValue([BENCH, FLY])
  vi.spyOn(exercises, 'getEquipment').mockResolvedValue(['Cable', 'Dumbbell'])
  vi.spyOn(exercises, 'createExercise').mockResolvedValue(FLY)
  vi.spyOn(exercises, 'updateExercise').mockResolvedValue(FLY)
  vi.spyOn(exercises, 'deleteExercise').mockResolvedValue(undefined)
})

afterEach(() => { vi.restoreAllMocks() })

describe('library tabs', () => {
  it('offers All plus a tab per template from the server', async () => {
    renderLibrary()
    expect(await screen.findByRole('button', { name: 'Chest Day' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Push A' })).toBeInTheDocument()
  })

  it('starts on All, which asks for the whole library', async () => {
    renderLibrary()
    expect(await screen.findByText('Flat DB Bench Press')).toBeInTheDocument()
    expect(exercises.getAllExercises).toHaveBeenLastCalledWith(undefined, undefined, undefined)
  })

  it('filters by the chosen template id', async () => {
    renderLibrary()
    fireEvent.click(await screen.findByRole('button', { name: 'Chest Day' }))
    await waitFor(() => expect(exercises.getAllExercises).toHaveBeenLastCalledWith(9, undefined, undefined))
  })
})

/**
 * Custom exercises with open-ended equipment (#358): a user adds their own,
 * with any equipment, and filters the library by it.
 */
describe('equipment', () => {
  it('filters by the equipment in use', async () => {
    renderLibrary()
    fireEvent.click(await screen.findByRole('button', { name: 'Cable' }))
    await waitFor(() => expect(exercises.getAllExercises).toHaveBeenLastCalledWith(undefined, undefined, 'Cable'))
  })

  it('suggests the equipment in use when adding, but takes anything', async () => {
    renderLibrary()
    fireEvent.click(await screen.findByRole('button', { name: 'Add exercise' }))
    const input = screen.getByLabelText('Equipment')
    const list = document.getElementById(input.getAttribute('list') ?? '')
    expect([...(list?.querySelectorAll('option') ?? [])].map(o => o.value)).toEqual(['Cable', 'Dumbbell'])
  })
})

describe('adding an exercise', () => {
  it('sends the new exercise and refreshes the library', async () => {
    renderLibrary()
    await screen.findByText('Flat DB Bench Press')
    fireEvent.click(screen.getByRole('button', { name: 'Add exercise' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Name'), { target: { value: 'Leg Press' } })
    fireEvent.change(within(dialog).getByLabelText('Muscles'), { target: { value: 'Quads, Glutes' } })
    fireEvent.change(within(dialog).getByLabelText('Equipment'), { target: { value: 'Machine' } })
    const calls = vi.mocked(exercises.getAllExercises).mock.calls.length
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(exercises.createExercise).toHaveBeenCalledWith({
      name: 'Leg Press', muscles: 'Quads, Glutes', type: 'weight', equip: 'Machine',
    }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(vi.mocked(exercises.getAllExercises).mock.calls.length).toBeGreaterThan(calls)
  })

  it('offers bodyweight as the type, and sends no muscles when left blank', async () => {
    renderLibrary()
    fireEvent.click(await screen.findByRole('button', { name: 'Add exercise' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Name'), { target: { value: 'Dead Hang' } })
    fireEvent.click(within(dialog).getByRole('radio', { name: 'Bodyweight' }))
    fireEvent.change(within(dialog).getByLabelText('Equipment'), { target: { value: 'Pull-up Bar' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(exercises.createExercise).toHaveBeenCalledWith({
      name: 'Dead Hang', muscles: null, type: 'bodyweight', equip: 'Pull-up Bar',
    }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it("shows the server's refusal and keeps the form open", async () => {
    vi.mocked(exercises.createExercise).mockRejectedValue(new Error('An exercise with that name already exists'))
    renderLibrary()
    fireEvent.click(await screen.findByRole('button', { name: 'Add exercise' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Name'), { target: { value: 'Push-Up' } })
    fireEvent.change(within(dialog).getByLabelText('Equipment'), { target: { value: 'Bodyweight' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('An exercise with that name already exists')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })
})

describe('your own exercises', () => {
  it('can be edited; built-ins cannot', async () => {
    renderLibrary()
    expect(await screen.findByRole('button', { name: 'Edit Cable Fly' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Edit Flat DB Bench Press' })).toBeNull()
  })

  it('saves an edit', async () => {
    renderLibrary()
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Cable Fly' }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByLabelText('Name')).toHaveValue('Cable Fly')
    fireEvent.change(within(dialog).getByLabelText('Name'), { target: { value: 'Low Cable Fly' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(exercises.updateExercise).toHaveBeenCalledWith(60, {
      name: 'Low Cable Fly', muscles: 'Chest', type: 'weight', equip: 'Cable',
    }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('deletes after confirming, explaining that logged ones are archived', async () => {
    renderLibrary()
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Cable Fly' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }))
    const confirm = screen.getByRole('alertdialog')
    expect(confirm).toHaveTextContent(/archived/i)
    expect(exercises.deleteExercise).not.toHaveBeenCalled()
    fireEvent.click(within(confirm).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(exercises.deleteExercise).toHaveBeenCalledWith(60))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })
})

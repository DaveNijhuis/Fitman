import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import LibraryPage from '../LibraryPage'
import * as templates from '../../api/templates'
import * as exercises from '../../api/exercises'

/**
 * "My days" in the Library (#359): build a day from the library, duplicate a
 * built-in to start from, hide the built-ins you don't use.
 */

const PUSH_A = { id: 1, name: 'Push A', focus: 'Chest · Shoulders · Triceps', colour: '#ff5a36', builtin: true, hidden: false }
const LEGS_B = { id: 6, name: 'Legs B', focus: null, colour: '#1f9d62', builtin: true, hidden: true }
const CHEST_DAY = { id: 9, name: 'Chest Day', focus: 'Chest', colour: '#8b5cf6', builtin: false, hidden: false }

const BENCH = { id: 5, name: 'Flat DB Bench Press', muscles: 'Chest', type: 'weight', equip: 'Dumbbell', custom: false, archived: false }
const FLY = { id: 60, name: 'Cable Fly', muscles: 'Chest', type: 'weight', equip: 'Cable', custom: true, archived: false }
const DIP = { id: 7, name: 'Chest Dip', muscles: 'Chest, Triceps', type: 'bodyweight', equip: 'Bodyweight', custom: false, archived: false }

function renderLibrary() {
  render(<MemoryRouter><LibraryPage /></MemoryRouter>)
}

async function myDays() {
  const heading = await screen.findByRole('heading', { name: 'My days' })
  return within(heading.closest('section') as HTMLElement)
}

beforeEach(() => {
  vi.spyOn(templates, 'getTemplates').mockResolvedValue([PUSH_A, LEGS_B, CHEST_DAY])
  vi.spyOn(templates, 'getTemplate').mockResolvedValue({ ...CHEST_DAY, exercises: [BENCH, FLY] })
  vi.spyOn(templates, 'createTemplate').mockResolvedValue({ ...CHEST_DAY, exercises: [] })
  vi.spyOn(templates, 'updateTemplate').mockResolvedValue({ ...CHEST_DAY, exercises: [] })
  vi.spyOn(templates, 'deleteTemplate').mockResolvedValue(undefined)
  vi.spyOn(templates, 'duplicateTemplate').mockResolvedValue({ ...PUSH_A, id: 10, name: 'Push A (copy)', builtin: false, exercises: [] })
  vi.spyOn(templates, 'setTemplateHidden').mockResolvedValue({ ...PUSH_A, hidden: true })
  vi.spyOn(exercises, 'getAllExercises').mockResolvedValue([BENCH, FLY, DIP])
  vi.spyOn(exercises, 'getEquipment').mockResolvedValue(['Cable', 'Dumbbell'])
})

afterEach(() => { vi.restoreAllMocks() })

describe('my days', () => {
  it('lists every day: built-ins to duplicate or hide, your own to edit', async () => {
    renderLibrary()
    const days = await myDays()
    expect(days.getByText('Push A')).toBeInTheDocument()
    expect(days.getByRole('button', { name: 'Duplicate Push A' })).toBeInTheDocument()
    expect(days.getByRole('button', { name: 'Hide Push A' })).toBeInTheDocument()
    expect(days.getByRole('button', { name: 'Show Legs B' })).toBeInTheDocument()
    expect(days.getByRole('button', { name: 'Edit Chest Day' })).toBeInTheDocument()
    expect(days.queryByRole('button', { name: 'Edit Push A' })).toBeNull()
  })

  it('duplicates a built-in and refreshes the list', async () => {
    renderLibrary()
    const days = await myDays()
    const calls = vi.mocked(templates.getTemplates).mock.calls.length
    fireEvent.click(days.getByRole('button', { name: 'Duplicate Push A' }))
    await waitFor(() => expect(templates.duplicateTemplate).toHaveBeenCalledWith(1))
    await waitFor(() => expect(vi.mocked(templates.getTemplates).mock.calls.length).toBeGreaterThan(calls))
  })

  it('hides and shows a built-in', async () => {
    renderLibrary()
    const days = await myDays()
    fireEvent.click(days.getByRole('button', { name: 'Hide Push A' }))
    await waitFor(() => expect(templates.setTemplateHidden).toHaveBeenCalledWith(1, true))
    fireEvent.click(days.getByRole('button', { name: 'Show Legs B' }))
    await waitFor(() => expect(templates.setTemplateHidden).toHaveBeenCalledWith(6, false))
  })
})

describe('building a day', () => {
  it('picks exercises from the library in order and saves the day', async () => {
    renderLibrary()
    fireEvent.click(await screen.findByRole('button', { name: 'New day' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Name'), { target: { value: 'Arm Day' } })
    fireEvent.click(await within(dialog).findByRole('button', { name: 'Add Chest Dip' }))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Add Cable Fly' }))
    fireEvent.click(within(dialog).getByRole('radio', { name: 'Violet' }))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(templates.createTemplate).toHaveBeenCalledWith({
      name: 'Arm Day', focus: null, colour: '#8b5cf6', exercise_ids: [7, 60],
    }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('offers each exercise once: an added one leaves the picker', async () => {
    renderLibrary()
    fireEvent.click(await screen.findByRole('button', { name: 'New day' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(await within(dialog).findByRole('button', { name: 'Add Chest Dip' }))
    expect(within(dialog).queryByRole('button', { name: 'Add Chest Dip' })).toBeNull()
    expect(within(dialog).getByRole('button', { name: 'Remove Chest Dip' })).toBeInTheDocument()
  })

  it('edits your day: loads its exercises, reorders, saves', async () => {
    renderLibrary()
    fireEvent.click(await (await myDays()).findByRole('button', { name: 'Edit Chest Day' }))
    const dialog = await screen.findByRole('dialog')
    expect(await within(dialog).findByRole('button', { name: 'Remove Cable Fly' })).toBeInTheDocument()
    expect(within(dialog).getByLabelText('Name')).toHaveValue('Chest Day')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Move Cable Fly up' }))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(templates.updateTemplate).toHaveBeenCalledWith(9, {
      name: 'Chest Day', focus: 'Chest', colour: '#8b5cf6', exercise_ids: [60, 5],
    }))
  })

  it("won't save a day with no exercises", async () => {
    renderLibrary()
    fireEvent.click(await screen.findByRole('button', { name: 'New day' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Name'), { target: { value: 'Empty' } })
    expect(within(dialog).getByRole('button', { name: 'Save' })).toBeDisabled()
  })

  it('deletes your day after confirming, saying past workouts stay', async () => {
    renderLibrary()
    fireEvent.click(await (await myDays()).findByRole('button', { name: 'Edit Chest Day' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }))
    const confirm = screen.getByRole('alertdialog')
    expect(confirm).toHaveTextContent(/past workouts/i)
    fireEvent.click(within(confirm).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(templates.deleteTemplate).toHaveBeenCalledWith(9))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })
})

import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ProgressPage from '../ProgressPage'
import * as progress from '../../api/progress'
import * as measurements from '../../api/measurements'
import * as features from '../../api/features'

/**
 * The body metrics list (#344): WLA25's muscle and bone mass appear, and the
 * WHR estimate no longer does. Fitman's WHR was far from the scale app's, and
 * WLA25 has no WHR formula, so an old stored value isn't offered either.
 */

const LATEST = {
  id: 2, recorded_at: '2026-09-22T08:00:00Z', weight_kg: 72.5, body_fat_pct: 18.5,
  bmi: 25.1, fat_mass_kg: 13.4, lean_mass_kg: 59.1, skeletal_muscle_kg: 33.5,
  muscle_mass_kg: 55.1, bone_mass_kg: 4.0, body_water_pct: 59.8, bmr_kcal: 1646,
  visceral_fat_grade: 4, body_age: 38, whr_estimate: 0.95,
}

beforeEach(() => {
  vi.spyOn(progress, 'getPRs').mockResolvedValue([])
  vi.spyOn(progress, 'getVolume').mockResolvedValue([])
  vi.spyOn(progress, 'getConsistency').mockResolvedValue([])
  vi.spyOn(progress, 'getBalance').mockResolvedValue([])
  vi.spyOn(measurements, 'getMeasurements').mockResolvedValue([LATEST] as never)
  vi.spyOn(features, 'getFeatures').mockResolvedValue({ scale: false })
})

afterEach(() => { vi.restoreAllMocks() })

async function metricsList() {
  render(<MemoryRouter><ProgressPage /></MemoryRouter>)
  const heading = await screen.findByText('Body metrics')
  return within(heading.closest('div.bg-\\[var\\(--color-surface\\)\\]') ?? document.body)
}

describe('body metrics', () => {
  it('lists muscle mass and bone mass', async () => {
    const list = await metricsList()
    expect(list.getByText('Muscle mass')).toBeInTheDocument()
    expect(list.getByText('55.1 kg')).toBeInTheDocument()
    expect(list.getByText('Bone mass')).toBeInTheDocument()
    expect(list.getByText('4.0 kg')).toBeInTheDocument()
  })

  it('no longer offers the WHR estimate, even for an old stored value', async () => {
    const list = await metricsList()
    expect(list.queryByText(/WHR/)).toBeNull()
  })
})

/**
 * Calendar colours come from each workout's template (#355), not a map of
 * three hard-coded names — so a user-made template gets its own colour, and a
 * workout whose template is gone falls back to the accent.
 */
describe('consistency calendar', () => {
  const WEEK = {
    week: '2026-W39',
    days: [
      { date: '2026-09-21', trained: true, session: 'Chest Day', colour: '#123456', volume_kg: null },
      { date: '2026-09-22', trained: true, session: 'Old Day', colour: null, volume_kg: null },
      { date: '2026-09-23', trained: false, session: null, colour: null, volume_kg: null },
    ],
  }

  async function renderCalendar() {
    vi.mocked(progress.getConsistency).mockResolvedValue([WEEK])
    render(<MemoryRouter><ProgressPage /></MemoryRouter>)
    return screen.findByTitle('2026-09-21 · Chest Day')
  }

  it("colours a day with its template's colour", async () => {
    const day = await renderCalendar()
    expect(day.style.background).toBe('rgba(18, 52, 86, 0.6)')
  })

  it('falls back to the accent for a workout with no template', async () => {
    await renderCalendar()
    expect(screen.getByTitle('2026-09-22 · Old Day').style.background).toBe('rgba(255, 90, 54, 0.6)')
  })

  it('lists the templates in view in the legend, each in its own colour', async () => {
    await renderCalendar()
    const swatch = screen.getByText('Chest Day').previousElementSibling as HTMLElement
    expect(swatch.style.background).toBe('rgb(18, 52, 86)')
    expect(screen.queryByText('Push A')).toBeNull()
  })
})

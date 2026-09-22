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

import { fetchAllPages, request } from './client'

export interface Measurement {
  id: number
  recorded_at: string
  weight_kg: number | null
  height_cm: number | null
  notes: string | null

  // Whole-body composition
  body_fat_pct: number | null
  bmi: number | null
  fat_mass_kg: number | null
  lean_mass_kg: number | null
  skeletal_muscle_kg: number | null
  fat_free_weight_kg: number | null
  body_water_pct: number | null
  protein_kg: number | null
  inorganic_salt_kg: number | null
  bmr_kcal: number | null
  visceral_fat_grade: number | null
  subcutaneous_fat_pct: number | null
  body_age: number | null
  whr_estimate: number | null
  smi: number | null

  // Segmental fat (kg)
  ra_fat_kg: number | null
  la_fat_kg: number | null
  trunk_fat_kg: number | null
  rl_fat_kg: number | null
  ll_fat_kg: number | null

  // Segmental muscle (kg)
  ra_muscle_kg: number | null
  la_muscle_kg: number | null
  trunk_muscle_kg: number | null
  rl_muscle_kg: number | null
  ll_muscle_kg: number | null

  // Raw impedance 20 kHz
  ra_z20: number | null
  la_z20: number | null
  rl_z20: number | null
  ll_z20: number | null
  trunk_z20: number | null

  // Raw impedance 100 kHz
  ra_z100: number | null
  la_z100: number | null
  rl_z100: number | null
  ll_z100: number | null
  trunk_z100: number | null
}

export interface MeasurementIn {
  recorded_at?: string
  weight_kg?: number | null
  height_cm?: number | null
  body_fat_pct?: number | null
  notes?: string | null
}

export function getMeasurements(): Promise<Measurement[]> {
  return fetchAllPages<Measurement>('/api/measurements')
}

export function logMeasurement(data: MeasurementIn): Promise<Measurement> {
  return request<Measurement>('/api/measurements', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export function deleteMeasurement(id: number): Promise<void> {
  return request<void>(`/api/measurements/${id}`, { method: 'DELETE' })
}

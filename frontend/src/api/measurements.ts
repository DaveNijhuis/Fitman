import type { components } from './schema'
import { fetchAllPages, request } from './client'

/**
 * Derived from the backend's published OpenAPI contract rather than
 * hand-written, so a response-shape change breaks the build instead of
 * surfacing as undefined at runtime (#268). The measurement record carries
 * around fifty BIA fields, which is precisely the shape nobody would notice
 * drifting by hand.
 */
export type Measurement = components['schemas']['MeasurementOut']
export type MeasurementIn = components['schemas']['MeasurementIn']

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

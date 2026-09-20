import type { components } from './schema'
import { fetchAllPages, request } from './client'

/**
 * Derived from the backend's published OpenAPI contract rather than
 * hand-written, so a response-shape change breaks the build instead of
 * surfacing as undefined at runtime (#268).
 */
export type CardioEntry = components['schemas']['CardioEntryOut']
export type CardioIn = components['schemas']['CardioIn']

export function getActivities(): Promise<string[]> {
  return request<string[]>('/api/cardio/activities')
}

export function getCardioHistory(): Promise<CardioEntry[]> {
  return fetchAllPages<CardioEntry>('/api/cardio')
}

export function logCardio(data: CardioIn): Promise<CardioEntry> {
  return request<CardioEntry>('/api/cardio', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export function deleteCardio(id: number): Promise<void> {
  return request<void>(`/api/cardio/${id}`, { method: 'DELETE' })
}

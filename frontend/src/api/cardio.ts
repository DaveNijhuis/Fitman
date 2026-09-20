import { fetchAllPages, request } from './client'

export interface CardioEntry {
  id: number
  session_id: number
  activity: string
  distance_m: number | null
  duration_s: number | null
  notes: string | null
  logged_at: string
}

export interface CardioIn {
  activity: string
  distance_m?: number | null
  duration_s?: number | null
  notes?: string | null
}

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

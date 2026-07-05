import { request } from './client'

export interface WorkoutSession {
  id: number
  session: string
  started_at: string
  ended_at: string | null
}

export interface WorkoutSessionSummary extends WorkoutSession {
  set_count: number
  volume_kg: number
}

export interface SessionLogEntry {
  id: number
  exercise_id: number
  exercise_name: string
  weight: number
  reps: number
  logged_at: string
}

const ACTIVE_KEY = 'fitman_active_workout'

export function saveActiveWorkout(id: number, session: string, startedAt: string) {
  localStorage.setItem(ACTIVE_KEY, JSON.stringify({ id, session, startedAt }))
}

export function clearActiveWorkout() {
  localStorage.removeItem(ACTIVE_KEY)
}

export function getActiveWorkout(): { id: number; session: string; startedAt: string } | null {
  try {
    const raw = localStorage.getItem(ACTIVE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

export function getHistory(): Promise<WorkoutSessionSummary[]> {
  return request<WorkoutSessionSummary[]>('/api/sessions')
}

export function getSessionLogs(sessionId: number): Promise<SessionLogEntry[]> {
  return request<SessionLogEntry[]>(`/api/sessions/${sessionId}/logs`)
}

export function startSession(session: string): Promise<WorkoutSession> {
  return request<WorkoutSession>('/api/sessions', {
    method: 'POST',
    body: JSON.stringify({ session }),
  })
}

export function endSession(sessionId: number): Promise<WorkoutSession> {
  return request<WorkoutSession>(`/api/sessions/${sessionId}/end`, {
    method: 'PATCH',
  })
}

export function discardSession(sessionId: number): Promise<void> {
  return request<void>(`/api/sessions/${sessionId}`, { method: 'DELETE' })
}

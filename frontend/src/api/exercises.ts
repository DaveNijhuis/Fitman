import type { components } from './schema'
import { request } from './client'

export type Exercise = components['schemas']['ExerciseOut']
/** A custom exercise to add; equipment is free text (#358). */
export type ExerciseIn = components['schemas']['ExerciseIn']
export type ExerciseUpdate = components['schemas']['ExerciseUpdate']

/**
 * The library, or one template's exercises in its order; either narrowed by
 * name and by equipment (matched regardless of case).
 */
export function getAllExercises(templateId?: number, search?: string, equip?: string): Promise<Exercise[]> {
  const params = new URLSearchParams()
  if (templateId !== undefined) params.set('template_id', String(templateId))
  if (search) params.set('search', search)
  if (equip) params.set('equip', equip)
  const qs = params.toString()
  return request<Exercise[]>(`/api/exercises${qs ? `?${qs}` : ''}`)
}

/** The equipment in the user's library: the filter, and suggestions when adding. */
export function getEquipment(): Promise<string[]> {
  return request<string[]>('/api/exercises/equipment')
}

export function createExercise(body: ExerciseIn): Promise<Exercise> {
  return request<Exercise>('/api/exercises', { method: 'POST', body: JSON.stringify(body) })
}

export function updateExercise(id: number, body: ExerciseUpdate): Promise<Exercise> {
  return request<Exercise>(`/api/exercises/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
}

/** Deletes it, or archives it if it has been logged: its history stays (#358). */
export function deleteExercise(id: number): Promise<void> {
  return request<void>(`/api/exercises/${id}`, { method: 'DELETE' })
}

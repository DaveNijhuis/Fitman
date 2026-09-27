import type { components } from './schema'
import { request } from './client'

export type Exercise = components['schemas']['ExerciseOut']

/** The library, or one template's exercises in its order; either narrowed by name. */
export function getAllExercises(templateId?: number, search?: string): Promise<Exercise[]> {
  const params = new URLSearchParams()
  if (templateId !== undefined) params.set('template_id', String(templateId))
  if (search) params.set('search', search)
  const qs = params.toString()
  return request<Exercise[]>(`/api/exercises${qs ? `?${qs}` : ''}`)
}

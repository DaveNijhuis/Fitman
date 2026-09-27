import { request } from './client'

export interface StrengthPoint {
  date: string
  estimated_1rm: number
}

export interface StrengthData {
  exercise_id: number
  exercise_name: string
  data: StrengthPoint[]
}

export interface VolumePoint {
  week: string
  volume_kg: number
}

export interface PersonalRecord {
  exercise_id: number
  exercise_name: string
  weight: number
  reps: number
  estimated_1rm: number
  date: string
}

export interface ConsistencyDay {
  date: string
  trained: boolean
  session: string | null
  /** The workout's template colour, "#rrggbb"; null once the template is gone (#355). */
  colour: string | null
  volume_kg: number | null
}

export interface ConsistencyWeek {
  week: string
  days: ConsistencyDay[]
}

export interface MuscleBalance {
  muscle: string
  percentage: number
}

export function getStrengthProgression(exerciseId: number): Promise<StrengthData> {
  return request<StrengthData>(`/api/progress/strength?exercise_id=${exerciseId}`)
}

export function getVolume(): Promise<VolumePoint[]> {
  return request<VolumePoint[]>('/api/progress/volume')
}

export function getPRs(): Promise<PersonalRecord[]> {
  return request<PersonalRecord[]>('/api/progress/prs')
}

export function getConsistency(): Promise<ConsistencyWeek[]> {
  return request<ConsistencyWeek[]>('/api/progress/consistency')
}

export function getBalance(): Promise<MuscleBalance[]> {
  return request<MuscleBalance[]>('/api/progress/balance')
}

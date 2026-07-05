import { request } from './client'

export interface Profile {
  username: string
  email: string | null
  display_name: string | null
  birth_year: number | null
  sex: string | null
  height_cm: number | null
  is_admin: boolean
}

export function getProfile(): Promise<Profile> {
  return request<Profile>('/api/profile')
}

export function updateProfile(data: {
  display_name?: string | null
  birth_year?: number | null
  sex?: 'male' | 'female' | 'other' | null
  height_cm?: number | null
}): Promise<Profile> {
  return request<Profile>('/api/profile', {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  return request<void>('/api/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  })
}

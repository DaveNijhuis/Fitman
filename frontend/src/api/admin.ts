import { request } from './client'

export interface AdminUser {
  id: number
  username: string
  email: string | null
  display_name: string | null
  is_active: boolean
  is_admin: boolean
  created_at: string
}

export function listUsers(): Promise<AdminUser[]> {
  return request<AdminUser[]>('/api/admin/users')
}

export function createUser(data: {
  username: string
  password: string
  email?: string | null
  display_name?: string | null
  is_admin?: boolean
}): Promise<AdminUser> {
  return request<AdminUser>('/api/admin/users', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function patchUser(id: number, data: { is_active?: boolean; is_admin?: boolean }): Promise<AdminUser> {
  return request<AdminUser>(`/api/admin/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function deleteUser(id: number): Promise<void> {
  return request<void>(`/api/admin/users/${id}`, { method: 'DELETE' })
}

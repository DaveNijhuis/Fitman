import { request, saveToken, clearToken } from './client'

interface TokenResponse {
  access_token: string
  token_type: string
}

export async function checkSetupRequired(): Promise<boolean> {
  const data = await request<{ required: boolean }>('/api/auth/setup-required')
  return data.required
}

export async function register(username: string, password: string, displayName?: string): Promise<void> {
  const data = await request<TokenResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password, display_name: displayName || undefined }),
  })
  saveToken(data.access_token)
}

export async function login(username: string, password: string): Promise<void> {
  const data = await request<TokenResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  saveToken(data.access_token)
}

export function logout(): void {
  clearToken()
}

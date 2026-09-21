import { request, saveToken, clearToken } from './client'

interface TokenResponse {
  access_token: string
  token_type: string
}

export async function checkSetupRequired(): Promise<boolean> {
  const data = await request<{ required: boolean }>('/api/auth/setup-required')
  return data.required
}

export async function register(username: string, password: string, displayName?: string, consentGiven = false): Promise<void> {
  const data = await request<TokenResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password, display_name: displayName || undefined, consent_given: consentGiven }),
  })
  saveToken(data.access_token)
}

export async function login(username: string, password: string): Promise<void> {
  // Logging in replaces the session, so drop the old token first. Sent along
  // with the credentials, a stale token would turn a wrong password's 401 into
  // an apparent expired session — clearing the form's error on redirect (#317).
  clearToken()
  const data = await request<TokenResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  saveToken(data.access_token)
}

export function logout(): void {
  clearToken()
}

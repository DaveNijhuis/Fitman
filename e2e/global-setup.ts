import { request } from '@playwright/test'

const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:8080'
export const ADMIN_USER = process.env.E2E_ADMIN_USER ?? 'e2e_admin'
export const ADMIN_PASS = process.env.E2E_ADMIN_PASS ?? 'E2eAdm1nP@ss99'

async function waitForHealth(baseURL: string, timeoutMs = 60_000): Promise<void> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      const api = await request.newContext({ baseURL })
      const resp = await api.get('/health')
      await api.dispose()
      if (resp.ok()) return
    } catch {
      // not up yet
    }
    await new Promise(r => setTimeout(r, 2000))
  }
  throw new Error(`App at ${baseURL} did not become healthy within ${timeoutMs}ms`)
}

export default async function globalSetup() {
  await waitForHealth(BASE_URL)

  const api = await request.newContext({ baseURL: BASE_URL })

  const setupCheck = await api.get('/api/auth/setup-required')
  const { required } = await setupCheck.json() as { required: boolean }

  if (required) {
    const resp = await api.post('/api/auth/register', {
      data: { username: ADMIN_USER, password: ADMIN_PASS, consent_given: true },
    })
    if (!resp.ok()) {
      throw new Error(`Admin registration failed: ${resp.status()} ${await resp.text()}`)
    }
  }

  await api.dispose()
}

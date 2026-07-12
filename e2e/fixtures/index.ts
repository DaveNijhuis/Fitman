import { test as base, request as baseRequest } from '@playwright/test'
import { ADMIN_USER, ADMIN_PASS } from '../global-setup'

export type TestUser = { username: string; password: string; token: string }

export const test = base.extend<{ testUser: TestUser }>({
  testUser: async ({}, use) => {
    const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:8080'
    const api = await baseRequest.newContext({ baseURL })

    const loginResp = await api.post('/api/auth/login', {
      data: { username: ADMIN_USER, password: ADMIN_PASS },
    })
    const { access_token: adminToken } = await loginResp.json() as { access_token: string }

    const username = `e2e_${Date.now()}`
    const password = 'E2eTest1234!'
    await api.post('/api/admin/users', {
      data: { username, password },
      headers: { Authorization: `Bearer ${adminToken}` },
    })

    const userLogin = await api.post('/api/auth/login', {
      data: { username, password },
    })
    const { access_token: token } = await userLogin.json() as { access_token: string }

    await use({ username, password, token })

    // Teardown — user may have already deleted their account via the UI
    await api.delete('/api/gdpr/erase', {
      headers: { Authorization: `Bearer ${token}` },
    })
    await api.dispose()
  },
})

export { expect } from '@playwright/test'

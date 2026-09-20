import { test as base, expect as baseExpect, request as baseRequest } from '@playwright/test'
import { ADMIN_USER, ADMIN_PASS } from '../global-setup'

export type TestUser = { username: string; password: string; token: string }

export const test = base.extend<{
  testUser: TestUser
  allowConsoleErrors: boolean
  failOnPageErrors: void
}>({
  /**
   * Opt out of the console.error assertion for a test that deliberately
   * exercises an error path. Uncaught exceptions still fail the test.
   *
   *   test.use({ allowConsoleErrors: true })
   */
  allowConsoleErrors: [false, { option: true }],

  /**
   * Fails any test whose page threw or logged an error (#269).
   *
   * Without this, a page that mounts and then dies on data load is
   * indistinguishable from a working one: assertions on headings pass before
   * the fetch resolves. That is how #267 shipped — ProgressPage crashed into
   * its ErrorBoundary while `progress.spec.ts` stayed green.
   *
   * Uncaught exceptions are always fatal. console.error is separated because
   * the browser logs failed requests there, so a test asserting on a 401 or a
   * 404 trips it legitimately — those opt out via `allowConsoleErrors`.
   *
   * Depending on `testUser` is deliberate and load-bearing. Playwright tears
   * fixtures down in reverse setup order, so this must be set up *after*
   * testUser to be torn down *before* it. Otherwise testUser's account erase
   * runs first, and any request the page still has in flight comes back 401 —
   * an error caused by teardown rather than by the test. ActiveWorkoutPage
   * requests a last-set per exercise concurrently, so it reliably has one
   * outstanding when a workout test ends.
   */
  failOnPageErrors: [async ({ page, allowConsoleErrors, testUser }, use) => {
    void testUser // referenced only to order teardown; see above

    const uncaught: string[] = []
    const logged: string[] = []
    page.on('pageerror', e => uncaught.push(e.message))
    page.on('console', m => {
      if (m.type() === 'error') logged.push(m.text())
    })

    await use()

    baseExpect(
      uncaught,
      `page threw ${uncaught.length} uncaught error(s):\n${uncaught.join('\n')}`,
    ).toEqual([])

    if (!allowConsoleErrors) {
      baseExpect(
        logged,
        `page logged ${logged.length} console error(s):\n${logged.join('\n')}\n` +
          'If this test deliberately exercises an error path, set ' +
          'test.use({ allowConsoleErrors: true }).',
      ).toEqual([])
    }
  }, { auto: true }],


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

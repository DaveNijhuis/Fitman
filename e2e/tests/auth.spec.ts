import { test, expect } from '../fixtures'
import { LoginPage } from '../pages/LoginPage'

test('unauthenticated visit to / redirects to /login', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/login/)
})

test.describe('failed login', () => {
  // The rejected login is a deliberate 401, which the browser logs as a
  // console error. Uncaught exceptions still fail this test.
  test.use({ allowConsoleErrors: true })

  test('wrong password shows error message', async ({ page }) => {
    const login = new LoginPage(page)
    await login.goto()
    await login.login('nonexistent_user', 'wrongpassword')
    await expect(login.error).toBeVisible()
  })
})

test('correct credentials redirect to home page', async ({ page, testUser }) => {
  const login = new LoginPage(page)
  await login.goto()
  await login.login(testUser.username, testUser.password)
  await login.waitForLoggedIn()
  await expect(page.getByTestId('stat-streak')).toBeVisible()
})

test.describe('rejected session (#317)', () => {
  // Every request the stale token makes is a deliberate 401, which the browser
  // logs as a console error. Uncaught exceptions still fail these tests.
  test.use({ allowConsoleErrors: true })

  test('a stale token returns the user to login, then back to their page', async ({ page, testUser }) => {
    // The state a re-keyed SECRET_KEY or an expired token leaves behind: a
    // token is stored, so the route guard lets the user through, but the
    // backend rejects every request made with it.
    await page.addInitScript(() => {
      if (!sessionStorage.getItem('seeded')) {
        localStorage.setItem('token', 'not.a.valid-token')
        sessionStorage.setItem('seeded', '1')
      }
    })

    await page.goto('/progress')

    await expect(page).toHaveURL(/\/login\?expired=1&next=%2Fprogress/)
    await expect(page.getByTestId('session-expired')).toBeVisible()
    await expect(page.getByText(/could not load data/i)).toHaveCount(0)

    const login = new LoginPage(page)
    await login.login(testUser.username, testUser.password)
    await expect(page).toHaveURL(/\/progress$/)
  })
})

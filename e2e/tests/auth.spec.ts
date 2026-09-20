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

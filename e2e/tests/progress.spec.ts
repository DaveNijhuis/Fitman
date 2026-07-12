import { test, expect } from '../fixtures'
import { LoginPage } from '../pages/LoginPage'

test.beforeEach(async ({ page, testUser }) => {
  const login = new LoginPage(page)
  await login.goto()
  await login.login(testUser.username, testUser.password)
  await login.waitForLoggedIn()
})

test('progress page loads', async ({ page }) => {
  await page.goto('/progress')
  await expect(page.getByRole('heading', { name: 'Progress' })).toBeVisible()
})

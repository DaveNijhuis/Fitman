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

test('manual measurement entry is offered and Weigh in is not, with the scale off (#326)', async ({ page }) => {
  // The E2E stack leaves SCALE_ENABLED at its default: off. The page asks
  // /api/features and must show nothing scale-related, not even the
  // "needs Web Bluetooth" note.
  const features = page.waitForResponse(r => r.url().endsWith('/api/features'))
  await page.goto('/progress')
  expect((await (await features).json()).scale).toBe(false)
  await expect(page.getByRole('button', { name: /log measurement/i })).toBeVisible()
  await expect(page.getByRole('button', { name: /weigh in/i })).toHaveCount(0)
  await expect(page.getByText(/web bluetooth/i)).toHaveCount(0)
})

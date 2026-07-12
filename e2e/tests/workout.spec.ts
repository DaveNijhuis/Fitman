import { test, expect } from '../fixtures'
import { LoginPage } from '../pages/LoginPage'
import { HomePage } from '../pages/HomePage'
import { WorkoutPage } from '../pages/WorkoutPage'

test.beforeEach(async ({ page, testUser }) => {
  const login = new LoginPage(page)
  await login.goto()
  await login.login(testUser.username, testUser.password)
  await login.waitForLoggedIn()
})

test('workout page loads after starting a session', async ({ page }) => {
  const home = new HomePage(page)
  await home.waitForStats()
  await home.startSession('Push A')

  const workout = new WorkoutPage(page)
  await workout.waitForLoaded()
  await expect(page).toHaveURL(/\/workout\/\d+/)
})

test('finishing a session returns to home', async ({ page }) => {
  const home = new HomePage(page)
  await home.waitForStats()
  await home.startSession('Push A')

  const workout = new WorkoutPage(page)
  await workout.waitForLoaded()
  await workout.finish()

  await expect(page.getByRole('heading', { name: /Fitman/i })).toBeVisible()
  await expect(page).not.toHaveURL(/\/workout\//)
})

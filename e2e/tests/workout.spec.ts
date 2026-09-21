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

test('a finished workout can be deleted from its detail page (#336)', async ({ page }) => {
  const home = new HomePage(page)
  await home.waitForStats()
  await home.startSession('Push A')
  const workout = new WorkoutPage(page)
  await workout.waitForLoaded()
  await workout.finish()

  await page.goto('/history')
  await expect(page.getByText('1 workouts logged')).toBeVisible()
  await page.getByRole('button', { name: /Push A/ }).click()
  await expect(page).toHaveURL(/\/history\/\d+/)

  await page.getByRole('button', { name: /delete workout/i }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('Push A')
  await dialog.getByRole('button', { name: /^delete$/i }).click()

  await expect(page).toHaveURL(/\/history$/)
  await expect(page.getByText('No workouts yet. Go lift something.')).toBeVisible()
  await expect(page.getByText('0 workouts logged')).toBeVisible()
})

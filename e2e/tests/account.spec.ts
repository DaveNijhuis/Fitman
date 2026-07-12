import { test, expect } from '../fixtures'
import { LoginPage } from '../pages/LoginPage'
import { SettingsPage } from '../pages/SettingsPage'

test.beforeEach(async ({ page, testUser }) => {
  const login = new LoginPage(page)
  await login.goto()
  await login.login(testUser.username, testUser.password)
  await login.waitForLoggedIn()
})

test('delete button is disabled until DELETE is typed', async ({ page }) => {
  const settings = new SettingsPage(page)
  await settings.goto()
  await settings.waitForLoaded()
  await settings.openDeletePanel()

  await expect(settings.deleteConfirmButton()).toBeDisabled()
  await settings.deleteConfirmInput().fill('delete')
  await expect(settings.deleteConfirmButton()).toBeDisabled()
  await settings.deleteConfirmInput().fill('DELETE')
  await expect(settings.deleteConfirmButton()).toBeEnabled()
})

test('account deletion removes account and redirects to login', async ({ page }) => {
  const settings = new SettingsPage(page)
  await settings.goto()
  await settings.waitForLoaded()
  await settings.deleteAccount()

  await expect(page).toHaveURL(/\/login/, { timeout: 10_000 })
})

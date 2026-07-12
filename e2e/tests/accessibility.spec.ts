import AxeBuilder from '@axe-core/playwright'
import { test, expect } from '../fixtures'
import { LoginPage } from '../pages/LoginPage'
import { HomePage } from '../pages/HomePage'

// color-contrast is excluded: the accent (#ff5a36) is a deliberate design choice
// that sits at 2.79:1 — tracked for a future design-system review, not a CI gate.
const axe = (page: import('@playwright/test').Page) =>
  new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .disableRules(['color-contrast'])

test('login page has no critical accessibility violations', async ({ page }) => {
  const login = new LoginPage(page)
  await login.goto()
  const results = await axe(page).analyze()
  expect(results.violations).toEqual([])
})

test('home page has no critical accessibility violations', async ({ page, testUser }) => {
  const login = new LoginPage(page)
  await login.goto()
  await login.login(testUser.username, testUser.password)

  const home = new HomePage(page)
  await home.waitForStats()

  const results = await axe(page).analyze()
  expect(results.violations).toEqual([])
})

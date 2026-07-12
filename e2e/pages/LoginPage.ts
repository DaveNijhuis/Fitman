import type { Page, Locator } from '@playwright/test'

export class LoginPage {
  readonly error: Locator

  constructor(private page: Page) {
    this.error = page.getByTestId('login-error')
  }

  async goto() {
    await this.page.goto('/login')
  }

  async login(username: string, password: string) {
    await this.page.getByLabel('Username').fill(username)
    await this.page.getByLabel('Password').fill(password)
    await this.page.getByRole('button', { name: 'Sign in' }).click()
  }

  async waitForLoggedIn() {
    // /login also has an <h1>Fitman</h1>, so we must wait for URL change, not the heading
    await this.page.waitForURL(url => !url.pathname.includes('/login'), { timeout: 10_000 })
  }
}

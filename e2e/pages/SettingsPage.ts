import type { Page } from '@playwright/test'

export class SettingsPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/settings')
  }

  async waitForLoaded() {
    await this.page.getByRole('heading', { name: 'Settings' }).waitFor({ state: 'visible' })
  }

  async openDeletePanel() {
    await this.page.getByRole('button', { name: 'Delete my account' }).click()
  }

  deleteConfirmInput() {
    return this.page.getByPlaceholder('DELETE')
  }

  deleteConfirmButton() {
    return this.page.getByRole('button', { name: 'Yes, delete everything' })
  }

  async deleteAccount() {
    await this.openDeletePanel()
    await this.deleteConfirmInput().fill('DELETE')
    await this.deleteConfirmButton().click()
  }
}

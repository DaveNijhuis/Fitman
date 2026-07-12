import type { Page } from '@playwright/test'

export class WorkoutPage {
  constructor(private page: Page) {}

  async waitForLoaded() {
    await this.page.getByRole('button', { name: 'Finish workout' }).waitFor({ state: 'visible' })
  }

  async finish() {
    await this.page.getByRole('button', { name: 'Finish workout' }).click()
    await this.page.getByRole('button', { name: 'Save & Finish' }).waitFor({ state: 'visible' })
    await this.page.getByRole('button', { name: 'Save & Finish' }).click()
  }
}

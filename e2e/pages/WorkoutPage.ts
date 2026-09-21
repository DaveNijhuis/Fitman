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
    // Finishing ends the session on the server, clears the in-progress marker,
    // then leaves the workout page. Returning earlier let a test navigate away
    // mid-way and find a stale "Resume" for a finished workout (#336 CI).
    await this.page.waitForURL(url => !url.pathname.startsWith('/workout'))
  }
}

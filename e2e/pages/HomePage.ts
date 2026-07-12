import type { Page, Locator } from '@playwright/test'

export class HomePage {
  readonly statStreak: Locator
  readonly statWeekWorkouts: Locator

  constructor(private page: Page) {
    this.statStreak = page.getByTestId('stat-streak')
    this.statWeekWorkouts = page.getByTestId('stat-week-workouts')
  }

  async goto() {
    await this.page.goto('/')
  }

  async waitForStats() {
    await this.statStreak.waitFor({ state: 'visible' })
  }

  async startSession(name: string) {
    await this.page.getByRole('button', { name: new RegExp(name) }).click()
  }
}

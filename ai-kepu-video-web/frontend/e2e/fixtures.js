import { test as base, expect } from '@playwright/test'

const apiBaseUrl = 'http://localhost:2002'

export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route(`${apiBaseUrl}/**`, async route => {
      const path = new URL(route.request().url()).pathname
      const body = path.endsWith('/config/readiness')
        ? { status: 'ready', can_continue: true, items: [] }
        : { data: [], items: [], total: 0 }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
    })
    await use(page)
  },
})

export { expect }

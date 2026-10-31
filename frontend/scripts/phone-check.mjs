// Viewport/theme check: signs in as every demo role and opens every screen in its navigation,
// failing on sideways page scroll, a crashed screen or a console error.
// Run against a served app, for example `npm run dev:mock -- --port 5199`, then:
//   node scripts/phone-check.mjs http://localhost:5199              phone width, light
//   node scripts/phone-check.mjs http://localhost:5199 1440         desktop width, light
//   node scripts/phone-check.mjs http://localhost:5199 360 --dark   phone width, dark
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'

// Playwright is not a project dependency; a global install works (NODE_PATH=$(npm root -g)).
const { chromium } = createRequire(import.meta.url)('playwright')

const base = process.argv[2] ?? 'http://localhost:5199'
const dark = process.argv.includes('--dark')
const width = Number(process.argv.find((arg, index) => index >= 3 && !arg.startsWith('--')) ?? 360)
const mobile = width <= 480
const fixtures = JSON.parse(readFileSync(new URL('../src/mocks/fixtures/generated.json', import.meta.url), 'utf8'))
const problems = []
let screens = 0

const browser = await chromium.launch()
for (const [role, boot] of Object.entries(fixtures.bootstrap)) {
  const context = await browser.newContext({
    viewport: { width, height: mobile ? 780 : 900 },
    deviceScaleFactor: mobile ? 2 : 1,
    isMobile: mobile,
    hasTouch: mobile,
    colorScheme: dark ? 'dark' : 'light',
  })
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => message.type() === 'error' && errors.push(message.text()))
  await page.goto(`${base}/login`)
  await page.click(`[data-testid="demo-${boot.user.email}"]`)
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 15000 })
  for (const item of boot.navigation) {
    errors.length = 0
    // Client-side navigation keeps the in-memory session, as a tap on the bottom bar would.
    await page.evaluate((path) => {
      window.history.pushState({}, '', path)
      window.dispatchEvent(new PopStateEvent('popstate'))
    }, item.path)
    await page.waitForTimeout(900)
    const state = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth - window.innerWidth,
      crashed: /Something went wrong|This screen failed/i.test(document.body.innerText),
      path: window.location.pathname,
    }))
    screens += 1
    if (state.overflow > 1) problems.push(`${role} ${item.path}: page scrolls sideways by ${state.overflow}px`)
    if (state.crashed) problems.push(`${role} ${item.path}: the screen crashed`)
    if (state.path !== item.path) problems.push(`${role} ${item.path}: ended up on ${state.path}`)
    for (const error of errors.filter((text) => !/Failed to load resource|favicon/i.test(text))) problems.push(`${role} ${item.path}: console error: ${error.slice(0, 160)}`)
  }
  await context.close()
}
await browser.close()

const label = `${width}px, ${dark ? 'dark' : 'light'}`
console.log(`Checked ${screens} screens at ${label}.`)
if (problems.length) {
  console.log(problems.join('\n'))
  process.exit(1)
}
console.log(`No sideways scroll, no crashed screens, no console errors, at ${label}.`)

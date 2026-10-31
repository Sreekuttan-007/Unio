// Scenario click-through: resets each demo scenario through the real reset endpoint and the
// Admin > Seed & Demo Data screen, then drives the UI as a judge would to confirm the staged
// story is actually visible on screen, not just that the reset call succeeded.
//
// Needs a real backend with demo mode on (dev_server.py, or any deployment with
// DEMO_MODE_ENABLED=true) - a reset is a real write, so this will not work against npm run
// dev:mock. Run two times in a row; both should pass cleanly, since a reset is idempotent.
//   node scripts/scenario-check.mjs http://localhost:5173
import { createRequire } from 'node:module'

// Playwright is not a project dependency; a global install works (NODE_PATH=$(npm root -g)).
const { chromium } = createRequire(import.meta.url)('playwright')

const base = process.argv[2] ?? 'http://localhost:5173'
const only = process.argv[3] // optional: run a single scenario id, e.g. "A"
const problems = []

const browser = await chromium.launch()

// Each sign-in gets its own context (no stored session), exactly like phone-check.mjs, so
// visiting /login never redirects away because of a token left over from the previous role.
async function signIn(email) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => message.type() === 'error' && errors.push(message.text()))
  await page.goto(`${base}/login`)
  await page.click(`[data-testid="demo-${email}"]`)
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 15000 })
  return { context, page, errors }
}

function check(label, condition) {
  if (!condition) problems.push(label)
}

async function visible(locator, timeout = 10000) {
  try {
    await locator.first().waitFor({ state: 'visible', timeout })
    return true
  } catch {
    return false
  }
}

function reportConsoleErrors(id, errors) {
  for (const error of errors.filter((text) => !/Failed to load resource|favicon/i.test(text))) problems.push(`${id}: console error: ${error.slice(0, 160)}`)
}

async function resetScenario(id) {
  const { context, page, errors } = await signIn('sysadmin@unio.demo')
  await page.goto(`${base}/w/system/seed`)
  await page.click(`[data-testid="scenario-${id}"] button`)
  check(`${id}: reset completed`, await visible(page.getByText(/The campus is back to Scenario/i), 20000))
  reportConsoleErrors(`${id} reset`, errors)
  await context.close()
}

// ---- Scenario A: exam room lost ------------------------------------------------------------
async function scenarioA() {
  await resetScenario('A')
  const { context, page, errors } = await signIn('facilities@unio.demo')
  await page.goto(`${base}/w/facilities/command`)
  check('A: Command Centre shows an open incident', await visible(page.getByText(/^INC-\d+/)))
  await page.goto(`${base}/w/facilities/simulator`)
  await page.click('button:has-text("Run simulation")')
  check('A: the simulator produced a read-only snapshot', await visible(page.getByText(/Read-only snapshot/i), 15000))
  check('A: at least one plan is shown', await visible(page.getByText(/^Plan [A-Z]:/)))
  reportConsoleErrors('A', errors)
  await context.close()
}

// ---- Scenario B: Wi-Fi outage ----------------------------------------------------------------
async function scenarioB() {
  await resetScenario('B')
  const { context, page, errors } = await signIn('facilities@unio.demo')
  await page.goto(`${base}/w/facilities/inbox`)
  const email = page.getByText(/Wi-Fi outage in ARB/i)
  check('B: the simulated email is waiting in the inbox', await visible(email))
  if (await email.first().isVisible().catch(() => false)) {
    await email.first().click()
    const button = page.getByRole('button', { name: 'Turn into a report' })
    if (await button.isVisible().catch(() => false)) {
      await button.click()
      check('B: the email was turned into a report or merged', await visible(page.getByText(/Became a report|Incident/i), 15000))
    }
  }
  // The webhook replay proof (C4): the built-in receiver changes nothing on a repeat.
  await page.goto(`${base}/w/system/integrations`)
  const sendTest = page.getByRole('button', { name: 'Send test' }).first()
  if (await sendTest.isVisible().catch(() => false)) {
    await sendTest.click()
    const first = await visible(page.getByText(/Delivered with a signature/i), 10000)
    await sendTest.click()
    const second = await visible(page.getByText(/Delivered with a signature/i), 10000)
    check('B: a webhook test delivers, twice, with no error', first && second)
  }
  reportConsoleErrors('B', errors)
  await context.close()
}

// ---- Scenario C: critical part out of stock ---------------------------------------------------
async function scenarioC() {
  await resetScenario('C')
  const { context, page, errors } = await signIn('procure@unio.demo')
  await page.goto(`${base}/w/procurement/queue`)
  const row = page.locator('[data-testid^="approval-APR-"]').first()
  check('C: a purchase request is waiting for Procurement', await visible(row))
  if (await row.isVisible().catch(() => false)) {
    await row.click()
    const approve = page.getByRole('button', { name: 'Approve' })
    if (await approve.isVisible().catch(() => false)) {
      await approve.click()
      check('C: the request can be approved without error', !(await visible(page.getByTestId('approval-error'), 2000)))
    }
  }
  await page.goto(`${base}/w/procurement/orders`)
  check('C: a purchase order now exists', await visible(page.getByText(/^PO-/)))
  reportConsoleErrors('C', errors)
  await context.close()
}

// ---- Scenario D: technician unavailable --------------------------------------------------------
async function scenarioD() {
  await resetScenario('D')
  const tech = await signIn('tech@unio.demo')
  await tech.page.goto(`${base}/w/technician/availability`)
  await tech.page.getByRole('button', { name: 'Sick' }).click()
  check('D: marking sick flags the open task for reassignment', await visible(tech.page.getByText(/flagged for reassignment/i), 10000))
  reportConsoleErrors('D (technician)', tech.errors)
  await tech.context.close()

  const facilities = await signIn('facilities@unio.demo')
  await facilities.page.goto(`${base}/w/facilities/technicians`)
  check('D: Facilities sees the technician as off sick', await visible(facilities.page.getByText(/Off sick/i)))
  reportConsoleErrors('D (facilities)', facilities.errors)
  await facilities.context.close()
}

const SCENARIOS = { A: scenarioA, B: scenarioB, C: scenarioC, D: scenarioD }
for (const [id, run] of Object.entries(SCENARIOS)) {
  if (only && only !== id) continue
  await run()
}

await browser.close()

console.log(`Checked scenario${only ? ` ${only}` : 's A-D'} against ${base}.`)
if (problems.length) {
  console.log(problems.join('\n'))
  process.exit(1)
}
console.log('Every scenario reset cleanly and its story is visible in the real UI.')

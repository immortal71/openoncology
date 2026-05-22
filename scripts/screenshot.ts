/**
 * Playwright screenshot script — captures all 6 demo pages at 1440x900.
 *
 * Usage:
 *   cd web && npx ts-node ../scripts/screenshot.ts
 *
 * Requires Playwright to be installed in the web project:
 *   npm install -D playwright @playwright/test
 *   npx playwright install chromium
 *
 * Output: docs/screenshots/{submit,results,repurposing,custom-drug,marketplace,crowdfund}.png
 */

import { chromium } from "playwright";
import * as path from "path";

const BASE_URL = process.env.SCREENSHOT_BASE_URL ?? "http://localhost:3000";
const DEMO_ID = "demo-nsclc-kras-g12c";
const OUT_DIR = path.resolve(__dirname, "../docs/screenshots");

const PAGES: { name: string; url: string }[] = [
  { name: "submit",      url: `${BASE_URL}/submit?demo=true` },
  { name: "results",     url: `${BASE_URL}/results/${DEMO_ID}?demo=true` },
  { name: "repurposing", url: `${BASE_URL}/repurposing/${DEMO_ID}?demo=true` },
  { name: "custom-drug", url: `${BASE_URL}/custom-drug/${DEMO_ID}?demo=true` },
  { name: "marketplace", url: `${BASE_URL}/marketplace?demo=true` },
  { name: "crowdfund",   url: `${BASE_URL}/crowdfund/${DEMO_ID}?demo=true` },
];

async function run() {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    colorScheme: "dark",
  });

  for (const page of PAGES) {
    const p = await context.newPage();
    console.log(`Capturing ${page.name} …`);
    await p.goto(page.url, { waitUntil: "domcontentloaded", timeout: 60_000 });
    // Give React time to hydrate and render
    await p.waitForTimeout(3_000);
    const dest = path.join(OUT_DIR, `${page.name}.png`);
    await p.screenshot({ path: dest, fullPage: false });
    console.log(`  → ${dest}`);
    await p.close();
  }

  await browser.close();
  console.log("\nDone — screenshots saved to docs/screenshots/");
}

run().catch((err) => { console.error(err); process.exit(1); });

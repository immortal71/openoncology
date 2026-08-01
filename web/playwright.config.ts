import { defineConfig, devices } from "@playwright/test";

const PORT = 3100;
const BASE_URL = `http://localhost:${PORT}`;

/**
 * E2E config. The app is booted in demo mode (NEXT_PUBLIC_ENABLE_DEMO_AUTH=1),
 * which bypasses Keycloak and serves the KRAS G12C demo case from
 * lib/demo-data.ts — so these tests need NO backend, DB, or auth server.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["html", { open: "never" }], ["list"]] : "list",
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    // Production build boots more deterministically in CI than `next dev`.
    command: "npm run build && npm run start -- --port " + PORT,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: {
      NEXT_PUBLIC_ENABLE_DEMO_AUTH: "1",
    },
  },
});

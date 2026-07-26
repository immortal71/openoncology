import { test, expect } from "@playwright/test";

const DEMO_ID = "demo-nsclc-kras-g12c";

/**
 * The submit -> results journey, driven entirely through demo mode so it needs
 * no backend. The submit page's real form POSTs to the API; the supported
 * backend-free path is its "View demo results" action, which routes to the
 * demo results page. We assert the full KRAS G12C case renders end to end.
 */
test.describe("submit -> results journey (demo mode)", () => {
  test("submit page loads and offers the live demo", async ({ page }) => {
    await page.goto("/submit");
    await expect(page.getByRole("heading", { name: /Submit Your Sample/i })).toBeVisible();
    // The cancer-type input is identified by its placeholder (the label has no
    // htmlFor association in the page markup).
    await expect(page.getByPlaceholder(/Lung adenocarcinoma/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /View demo results/i })).toBeVisible();
  });

  test("View demo results navigates to the rendered KRAS G12C case", async ({ page }) => {
    await page.goto("/submit");
    await page.getByRole("button", { name: /View demo results/i }).click();

    await expect(page).toHaveURL(new RegExp(`/results/${DEMO_ID}`));

    // Core evidence surfaced by the demo results page.
    await expect(page.getByText("Non-Small Cell Lung Cancer").first()).toBeVisible();
    await expect(page.getByText("KRAS").first()).toBeVisible();
    // Top-ranked drug candidate from DEMO_REPURPOSING.
    await expect(page.getByText(/Sotorasib/i).first()).toBeVisible();
  });

  test("direct navigation to the demo results id renders the mutation table", async ({ page }) => {
    await page.goto(`/results/${DEMO_ID}`);
    // The KRAS G12C variant (p.Gly12Cys) appears in the mutation table.
    await expect(page.getByText(/p\.Gly12Cys/).first()).toBeVisible();
    await expect(page.getByText(/Sotorasib/i).first()).toBeVisible();
  });
});

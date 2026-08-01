import { test, expect } from "@playwright/test";

test.describe("home page", () => {
  test("renders the landing page with the product title", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/OpenOncology/);
    // The brand name appears somewhere in the hero/body copy.
    await expect(page.getByText(/OpenOncology/i).first()).toBeVisible();
  });

  test("does not surface a Next.js error overlay on load", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("text=Application error")).toHaveCount(0);
    await expect(page.locator("text=Unhandled Runtime Error")).toHaveCount(0);
  });
});

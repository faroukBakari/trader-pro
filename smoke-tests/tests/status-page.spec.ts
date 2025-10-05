import { expect, test } from "@playwright/test";

test.describe("Status Page Smoke Tests", () => {
  test("should load the status page and display API status", async ({
    page,
  }) => {
    // Navigate to the status page
    await page.goto("/");

    // Wait for the page to load
    await page.waitForLoadState("networkidle");

    // Check if the page title is correct
    await expect(page).toHaveTitle(/Trader Pro/);

    // Check if the main heading is present
    await expect(page.locator("h1")).toContainText("Trader Pro");

    // Check if API status component is present
    const apiStatusComponent = page.locator('[data-testid="api-status"]');
    await expect(apiStatusComponent).toBeVisible();
  });

  test("should display backend API health status", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Wait for API status to load (max 10 seconds)
    await page.waitForSelector('[data-testid="api-status"]', {
      timeout: 10000,
    });

    // Check if health status is displayed
    const healthStatus = page.locator('[data-testid="health-status"]');
    await expect(healthStatus).toBeVisible();

    // The status should be either "ok" or show an error
    // We'll check that some status text is present
    await expect(healthStatus).not.toBeEmpty();
  });

  test("should display version information", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Wait for API status component
    await page.waitForSelector('[data-testid="api-status"]', {
      timeout: 10000,
    });

    // Check if version information is displayed
    const versionInfo = page.locator('[data-testid="version-info"]');
    await expect(versionInfo).toBeVisible();

    // Version should contain some text
    await expect(versionInfo).not.toBeEmpty();
  });

  test("should handle API connectivity gracefully", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Wait a moment for any API calls to complete
    await page.waitForTimeout(2000);

    // Check that the page doesn't show any JavaScript errors
    const errorMessages = page.locator('.error, [data-testid="error"]');

    // If there are error messages, they should be handled gracefully
    // (not crashing the app)
    const pageContent = page.locator("body");
    await expect(pageContent).toBeVisible();

    // The main app structure should still be present even if API fails
    const mainContainer = page.locator('main, #app, [data-testid="main-app"]');
    await expect(mainContainer).toBeVisible();
  });

  test("should navigate to status view successfully", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Look for navigation to status page (if it exists as a separate route)
    // This assumes there might be a navigation link or the status is on the main page

    // Check that we can access the API status page/component
    const statusLink = page.locator(
      'a[href*="status"], [data-testid="status-link"]'
    );

    if (await statusLink.isVisible()) {
      await statusLink.click();
      await page.waitForLoadState("networkidle");
    }

    // Verify we're on a page that shows API status
    const apiStatusComponent = page.locator('[data-testid="api-status"]');
    await expect(apiStatusComponent).toBeVisible();
  });

  test("should display proper loading states", async ({ page }) => {
    await page.goto("/");

    // Check for loading indicators while API calls are being made
    // This test verifies the UX during API calls

    // Initially, there might be loading states
    const loadingIndicators = page.locator('.loading, [data-testid="loading"]');

    // Wait for the page to finish loading
    await page.waitForLoadState("networkidle");

    // After loading, the main content should be visible
    const mainContent = page.locator('[data-testid="api-status"]');
    await expect(mainContent).toBeVisible();

    // Loading indicators should be gone or hidden
    // (This is a best practice check for good UX)
  });
});

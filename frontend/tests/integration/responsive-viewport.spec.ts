import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers";

test.describe("Phase 12.3 — Viewport Sanity (Mobile & Tablet Layouts)", () => {
  test.use({ viewport: { width: 390, height: 844 } }); // iPhone 13 / Modern mobile viewport

  test("renders authenticated operational console cleanly on mobile viewport without layout breakage", async ({
    page,
  }) => {
    // 1. Log in via mobile viewport
    await loginAs(page, "admin", "adminpassword123");

    // 2. Verify header and live indicator adapt on mobile
    await expect(page.getByText("Console", { exact: true })).toBeVisible();
    await expect(page.getByText(/Live WS Sync|Polling Fallback/i)).toBeVisible();

    // 3. Verify KPI cards wrap gracefully
    await expect(page.getByRole("main").getByText("Worker Fleet")).toBeVisible();
    await expect(page.getByText("Current Throughput")).toBeVisible();

    // 4. Verify Task Backlog adapts to mobile scrolling
    await page.goto("/tasks");
    await expect(page.getByRole("heading", { name: "Task Backlog" })).toBeVisible();
    await expect(page.getByPlaceholder("e.g. default, reports")).toBeVisible();
  });
});

import { test, expect } from "@playwright/test";
import { loginAs, getBackendCookies, BASE_API_URL } from "./helpers";

test.describe("Phase 12.1 — Multi-Tenant Data Isolation (No Cross-Tenant Leakage)", () => {
  test("strictly isolates tasks between Tenant A and Tenant B across UI and REST API", async ({
    page,
    browser,
  }) => {
    const userA = "tenant_user_a";
    const userB = "tenant_user_b";
    const pwd = "Password123!";

    // Unique task identifier created by Tenant A
    const tenantATaskType = `alpha.classified.${Date.now()}`;

    // ── STEP 1: Tenant A Logs In & Dispatches Task ──────────────────────
    await loginAs(page, userA, pwd);

    // Verify tenant badge in sidebar shows tenant_a
    await expect(page.locator("aside")).toContainText("tenant: tenant_a", { timeout: 10000 });

    // Submit task via UI
    await page.getByRole("button", { name: /Submit Task/i }).click();
    await page.getByPlaceholder("e.g. email.send or reports.daily").fill(tenantATaskType);
    await page.locator('form button[type="submit"]').click();

    // Verify task is visible on Tenant A's dashboard and backlog
    await expect(page.getByText(tenantATaskType)).toBeVisible({ timeout: 10000 });

    await page.goto("/tasks");
    await expect(page.getByText(tenantATaskType)).toBeVisible({ timeout: 10000 });

    // Log out Tenant A
    await page.getByRole("button", { name: /Sign Out/i }).click();
    await page.waitForURL(/\/login/, { timeout: 10000 });

    // ── STEP 2: Tenant B Logs In & Verifies Zero Leakage ─────────────────
    // Use an isolated browser context to ensure no leaked cookie or state
    const contextB = await browser.newContext();
    const pageB = await contextB.newPage();

    await loginAs(pageB, userB, pwd);

    // Verify tenant badge in sidebar shows tenant_b
    await expect(pageB.locator("aside")).toContainText("tenant: tenant_b");

    // Navigate to /tasks backlog
    await pageB.goto("/tasks");

    // CRITICAL ASSERTION: Tenant A's task must NEVER appear in Tenant B's backlog
    await expect(pageB.getByText(tenantATaskType)).not.toBeVisible();

    // Verify directly through backend API with Tenant B's credentials
    const cookiesB = await getBackendCookies(userB, pwd);
    const tasksRes = await fetch(`${BASE_API_URL}/tasks?limit=50`, {
      headers: { Cookie: cookiesB },
    });
    const tasksData = await tasksRes.json();
    const leakedTask = tasksData.items.find(
      (t: { task_type: string }) => t.task_type === tenantATaskType
    );

    // Zero cross-tenant data leakage confirmed
    expect(leakedTask).toBeUndefined();

    // ── STEP 3: Tenant B Creates Their Own Task ────────────────────────
    const tenantBTaskType = `beta.proprietary.${Date.now()}`;
    await pageB.goto("/dashboard");
    await pageB.getByRole("button", { name: /Submit Task/i }).click();
    await pageB.getByPlaceholder("e.g. email.send or reports.daily").fill(tenantBTaskType);
    await pageB.locator('form button[type="submit"]').click();

    // Verify Tenant B sees their own task
    await expect(pageB.getByText(tenantBTaskType)).toBeVisible({ timeout: 10000 });

    await contextB.close();
  });
});

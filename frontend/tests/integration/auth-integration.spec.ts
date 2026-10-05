import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers";

test.describe("Phase 12.1 — Authentication Integration (Real Backend)", () => {
  test("authenticates admin user against real FastAPI backend and renders operational dashboard", async ({
    page,
  }) => {
    // Perform real login
    await loginAs(page, "admin", "adminpassword123");

    // Verify current user details in the sidebar
    await expect(page.locator("aside")).toContainText("admin");
    await expect(page.locator("aside")).toContainText("tenant: default");

    // Verify dashboard cards rendered real database metrics
    await expect(page.getByRole("main").getByText("Worker Fleet")).toBeVisible();
    await expect(page.getByText("Configured Queues")).toBeVisible();
    await expect(page.getByText("Current Throughput")).toBeVisible();
  });

  test("rejects invalid credentials with real 401 error envelope from backend", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.getByPlaceholder("admin or user@domain.com").fill("admin");
    await page.getByPlaceholder("••••••••••••").fill("IncorrectPassword123!");
    await page.getByRole("button", { name: /Sign In/i }).click();

    // Verify real error message returned from backend
    await expect(page.getByText(/Invalid username or password/i)).toBeVisible({
      timeout: 10000,
    });
    expect(page.url()).toContain("/login");
  });

  test("sign out revokes active session and redirects back to login page", async ({
    page,
  }) => {
    await loginAs(page, "admin", "adminpassword123");

    // Click Sign Out button
    const signOutBtn = page.getByRole("button", { name: /Sign Out/i });
    await expect(signOutBtn).toBeVisible();
    await signOutBtn.click();

    // Verify redirected back to /login
    await page.waitForURL(/\/login/, { timeout: 10000 });
    await expect(page.getByRole("button", { name: /Sign In/i })).toBeVisible();
  });
});

import { test, expect } from "@playwright/test";

test.describe("Authentication Flows", () => {
  test("renders login form with proper accessibility and fields", async ({ page }) => {
    await page.goto("/login");

    await expect(page.getByText("Task Engine Console")).toBeVisible();
    await expect(page.getByText("Enter your credentials to access the distributed task operations console")).toBeVisible();
    await expect(page.getByPlaceholder("admin or user@domain.com")).toBeVisible();
    await expect(page.getByPlaceholder("••••••••••••")).toBeVisible();
    await expect(page.getByRole("button", { name: /Sign In/i })).toBeVisible();
  });

  test("displays error message on invalid credentials", async ({ page }) => {
    // Intercept login API to simulate invalid credentials
    await page.route("**/api/v1/auth/login", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "UNAUTHENTICATED",
            message: "Invalid username or password.",
          },
        }),
      });
    });

    await page.goto("/login");
    await page.getByPlaceholder("admin or user@domain.com").fill("wrong_user");
    await page.getByPlaceholder("••••••••••••").fill("bad_password");
    await page.getByRole("button", { name: /Sign In/i }).click();

    await expect(page.getByText(/Invalid username or password/i)).toBeVisible();
    expect(page.url()).toContain("/login");
  });

  test("authenticates successfully and redirects to /dashboard", async ({ page }) => {
    // Mock all backend API calls for the authenticated session
    await page.route("**/api/v1/**", async (route) => {
      const url = route.request().url();
      if (url.includes("/auth/login")) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            access_token: "mock-jwt-token-val",
            token_type: "bearer",
            role: "operator",
            user: {
              id: "user-123",
              username: "operator_jane",
              role: "operator",
            },
          }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [],
          total: 0,
          has_more: false,
          points: [],
          current_incoming_tps: 0,
          current_outgoing_tps: 0,
        }),
      });
    });

    await page.goto("/login");
    await page.getByPlaceholder("admin or user@domain.com").fill("operator_jane");
    await page.getByPlaceholder("••••••••••••").fill("SecurePass123!");
    await page.getByRole("button", { name: /Sign In/i }).click();

    // Verify redirected to dashboard
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 });
  });
});

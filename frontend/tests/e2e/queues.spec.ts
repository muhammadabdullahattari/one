import { test, expect } from "@playwright/test";

test.describe("Queue Management Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/queues**", async (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            queue_name: "notifications",
            broker_backend: "native",
            max_concurrency: 20,
            rate_limit_rps: 100,
          }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              queue_name: "high-priority",
              broker_backend: "redis",
              max_concurrency: 50,
              rate_limit_rps: 200,
              depth: 12,
              status: "active",
              oldest_task_age: 0.5,
            },
            {
              queue_name: "background-reports",
              broker_backend: "native",
              max_concurrency: 10,
              rate_limit_rps: 50,
              depth: 3,
              status: "active",
              oldest_task_age: 12.4,
            },
          ],
        }),
      });
    });
  });

  test("renders queue roster and configuration metrics", async ({ page }) => {
    await page.goto("/queues");

    await expect(page.getByRole("heading", { name: "Queue Configuration" })).toBeVisible();
    await expect(page.getByText("high-priority")).toBeVisible();
    await expect(page.getByText("background-reports")).toBeVisible();
    await expect(page.getByText("Backend: redis")).toBeVisible();
    await expect(page.getByText("200 RPS")).toBeVisible();
  });

  test("creates a new queue through modal dialog", async ({ page }) => {
    await page.goto("/queues");
    await page.getByRole("button", { name: "Create Queue" }).click();

    await expect(page.getByText("Create New Task Queue")).toBeVisible();
    await page.getByPlaceholder("e.g. notifications, billing").fill("notifications");
    await page.locator("form").getByRole("button", { name: "Save Queue" }).click();

    await expect(page.getByText("Create New Task Queue")).not.toBeVisible();
  });
});

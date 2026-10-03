import { test, expect } from "@playwright/test";

test.describe("Tasks Backlog Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/tasks**", async (route) => {
      const url = new URL(route.request().url());
      const queue = url.searchParams.get("queue");
      const status = url.searchParams.get("status");

      let items = [
        {
          task_id: "task-001",
          task_type: "email.send_welcome",
          queue: "default",
          status: "SUCCEEDED",
          status_reason: "Delivered in 240ms",
          created_at: new Date().toISOString(),
          retries: 0,
          max_retries: 3,
        },
        {
          task_id: "task-002",
          task_type: "report.generate_pdf",
          queue: "reports",
          status: "RUNNING",
          status_reason: null,
          created_at: new Date().toISOString(),
          retries: 1,
          max_retries: 3,
        },
      ];

      if (queue) {
        items = items.filter((i) => i.queue === queue);
      }
      if (status) {
        items = items.filter((i) => i.status === status);
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items,
          total: items.length,
          offset: 0,
          limit: 50,
          has_more: false,
        }),
      });
    });
  });

  test("renders tasks page and displays virtualized table entries", async ({ page }) => {
    await page.goto("/tasks");

    await expect(page.getByRole("heading", { name: "Task Backlog" })).toBeVisible();
    await expect(page.getByText("DOM-virtualized high-concurrency execution ledger")).toBeVisible();

    // Table headers
    await expect(page.getByText("TASK IDENTIFIER / TYPE")).toBeVisible();
    await expect(page.getByText("QUEUE", { exact: true })).toBeVisible();
    await expect(page.getByText("LIFECYCLE STATUS & EXPLANATION")).toBeVisible();

    // Items
    await expect(page.getByText("email.send_welcome")).toBeVisible();
    await expect(page.getByText("task-001")).toBeVisible();
    await expect(page.getByText("report.generate_pdf")).toBeVisible();
    await expect(page.getByText("task-002")).toBeVisible();
  });

  test("filters task list by queue and status", async ({ page }) => {
    await page.goto("/tasks");

    // Select status filter
    await page.locator("select").selectOption("RUNNING");
    await expect(page.getByText("report.generate_pdf")).toBeVisible();
    await expect(page.getByText("email.send_welcome")).not.toBeVisible();

    // Reset filters
    await page.getByRole("button", { name: "Reset Filters" }).click();
    await expect(page.getByText("email.send_welcome")).toBeVisible();
    await expect(page.getByText("report.generate_pdf")).toBeVisible();
  });
});

import { test, expect } from "@playwright/test";

test.describe("Dead Letter Queue (DLQ) Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/dlq**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              dlq_id: "dlq-entry-99",
              task_id: "task-poison-pill-404",
              final_attempt_id: "attempt-1",
              queue: "high-priority",
              error_class: "FatalException",
              reason: "ZeroDivisionError in calculate_fee",
              payload_ref: null,
              dead_at: new Date().toISOString(),
              replay_count: 0,
              last_replayed_at: null,
            },
          ],
          total: 1,
          limit: 25,
          offset: 0,
        }),
      });
    });
  });

  test("renders DLQ page with poison pill tasks and failure reasons", async ({ page }) => {
    await page.goto("/dlq");

    await expect(page.getByRole("heading", { name: "Dead Letter Queue (DLQ)" })).toBeVisible();
    await expect(page.locator('a[href="/tasks/task-poison-pill-404"]').first()).toBeVisible();
    await expect(page.getByText("FatalException")).toBeVisible();
    await expect(page.getByText("high-priority")).toBeVisible();
  });

  test("replays dead-letter task back into active queue", async ({ page }) => {
    await page.route("**/api/v1/dlq/dlq-entry-99/replay", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          message: "Task successfully requeued.",
          task_id: "task-poison-pill-404",
        }),
      });
    });

    await page.goto("/dlq");
    const replayBtn = page.getByRole("button", { name: "Replay", exact: true });
    await expect(replayBtn).toBeVisible();
    await replayBtn.click();
    await expect(page.getByText(/successfully replayed into active queue/i)).toBeVisible();
  });
});

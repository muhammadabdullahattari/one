import { test, expect } from "@playwright/test";

test.describe("Worker Fleet Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/workers**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              worker_id: "worker-prod-alpha-1",
              hostname: "k8s-pod-worker-01",
              process_id: 1042,
              status: "active",
              concurrency: 8,
              active_task_count: 2,
              queues: ["default"],
              last_heartbeat: new Date().toISOString(),
              version: "1.0.0",
              capabilities: {},
              registered_at: new Date().toISOString(),
              drained_at: null,
            },
          ],
        }),
      });
    });
  });

  test("renders worker fleet cards and resource utilization", async ({ page }) => {
    await page.goto("/workers");

    await expect(page.getByRole("heading", { name: "Worker Fleet" })).toBeVisible();
    await expect(page.getByText("worker-prod-alpha-1")).toBeVisible();
    await expect(page.getByText("k8s-pod-worker-01 • PID 1042")).toBeVisible();
    await expect(page.getByText("2 / 8")).toBeVisible();
  });

  test("allows triggering worker draining", async ({ page }) => {
    await page.route("**/api/v1/workers/worker-prod-alpha-1/drain", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "Worker drain signal queued." }),
      });
    });

    await page.goto("/workers");
    const drainBtn = page.getByRole("button", { name: /Graceful Drain/i });
    await expect(drainBtn).toBeVisible();
    await drainBtn.click();
  });
});

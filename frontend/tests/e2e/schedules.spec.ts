import { test, expect } from "@playwright/test";

test.describe("Recurring Schedules Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/schedules**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              schedule_id: "sched-nightly-backup",
              task_type: "database.backup_nightly",
              queue: "default",
              cron: "0 2 * * *",
              interval_seconds: null,
              timezone: "UTC",
              misfire_policy: "coalesce",
              enabled: true,
              payload: {},
              next_run_at: new Date(Date.now() + 3600000).toISOString(),
              last_run_at: new Date(Date.now() - 3600000).toISOString(),
              total_run_count: 42,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
          ],
          total: 1,
        }),
      });
    });

    await page.route("**/api/v1/queues**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [{ queue_name: "default" }],
        }),
      });
    });
  });

  test("renders scheduled tasks and cron timings", async ({ page }) => {
    await page.goto("/schedules");

    await expect(page.getByRole("heading", { name: "Recurring Schedules" })).toBeVisible();
    await expect(page.getByText("database.backup_nightly")).toBeVisible();
    await expect(page.getByText('cron("0 2 * * *")')).toBeVisible();
  });

  test("triggers manual schedule run immediately", async ({ page }) => {
    await page.route("**/api/v1/schedules/sched-nightly-backup/trigger", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          task_id: "task-spawned-backup-777",
          status: "QUEUED",
        }),
      });
    });

    await page.goto("/schedules");
    const triggerBtn = page.getByRole("button", { name: "Trigger Now" });
    await expect(triggerBtn).toBeVisible();
    await triggerBtn.click();
    await expect(page.getByText(/Spawned Task ID: task-spawned-backup-777/i)).toBeVisible();
  });
});

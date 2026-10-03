import { test, expect } from "@playwright/test";

test.describe("Dashboard Telemetry & Operations", () => {
  test.beforeEach(async ({ page }) => {
    // Mock the backend API responses for stable testing
    await page.route("**/api/v1/tasks**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              task_id: "task-abc-123",
              task_type: "email.send_welcome",
              queue: "default",
              status: "SUCCEEDED",
              status_reason: "Delivered in 210ms",
              created_at: new Date().toISOString(),
              retries: 0,
              max_retries: 3,
            },
          ],
          total: 1,
          has_more: false,
        }),
      });
    });

    await page.route("**/api/v1/queues**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              name: "default",
              depth: 42,
              status: "active",
              oldest_task_age: 1.5,
            },
            {
              name: "high-priority",
              depth: 8,
              status: "active",
              oldest_task_age: 0.2,
            },
          ],
        }),
      });
    });

    await page.route("**/api/v1/workers**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              worker_id: "worker-prod-01",
              hostname: "node-us-east-1",
              status: "active",
              concurrency: 16,
              active_task_count: 5,
              heartbeat: new Date().toISOString(),
              last_heartbeat: new Date().toISOString(),
              queues: ["default"],
              version: "1.0.0",
              process_id: 1001,
            },
          ],
        }),
      });
    });

    await page.route("**/api/v1/dlq**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [],
          total: 3,
        }),
      });
    });

    await page.route("**/api/v1/analytics/throughput**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          current_incoming_tps: 154,
          current_outgoing_tps: 149,
          points: [
            {
              timestamp: new Date().toISOString(),
              incoming_rate: 154,
              outgoing_rate: 149,
            },
          ],
        }),
      });
    });
  });

  test("renders operational overview with KPI metrics and chart canvas", async ({ page }) => {
    await page.goto("/dashboard");

    await expect(page.getByRole("heading", { name: "Operational Overview" })).toBeVisible();
    await expect(page.getByText("1 Active")).toBeVisible();
    await expect(page.getByText("2 Queues")).toBeVisible();
    await expect(page.getByText("154 TPS")).toBeVisible();
    await expect(page.getByText("3 Tasks")).toBeVisible();

    // Chart header
    await expect(page.getByText("Throughput Telemetry (Incoming vs Outgoing)")).toBeVisible();

    // Recent task row
    await expect(page.getByText("email.send_welcome")).toBeVisible();
    await expect(page.getByText("task-abc-123")).toBeVisible();
  });

  test("opens submit task modal and dispatches task", async ({ page }) => {
    await page.route("**/api/v1/tasks", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            task_id: "task-new-999",
            task_type: "report.generate_pdf",
            queue: "default",
            status: "PENDING",
            created_at: new Date().toISOString(),
          }),
        });
      } else {
        await route.fallback();
      }
    });

    await page.goto("/dashboard");
    await page.getByRole("button", { name: /Submit Task/i }).click();

    // Check modal visibility
    await expect(page.getByText("Submit New Task")).toBeVisible();
    await page.getByPlaceholder("e.g. email.send or reports.daily").fill("report.generate_pdf");
    await page.locator("form").getByRole("button", { name: "Submit Task" }).click();

    // Verify modal closes
    await expect(page.getByText("Submit New Task")).not.toBeVisible();
  });
});

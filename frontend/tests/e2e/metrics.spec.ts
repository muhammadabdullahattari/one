import { test, expect } from "@playwright/test";

test.describe("Telemetry & Analytics Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/analytics/throughput**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          current_incoming_tps: 180,
          current_outgoing_tps: 175,
          points: [
            {
              timestamp: new Date().toISOString(),
              incoming_rate: 180,
              outgoing_rate: 175,
            },
          ],
        }),
      });
    });

    await page.route("**/api/v1/analytics/latency**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          queue_wait: { p50_ms: 5.1, p95_ms: 18.2, p99_ms: 45.0, avg_ms: 7.2 },
          execution_duration: { p50_ms: 14.2, p95_ms: 48.7, p99_ms: 112.5, avg_ms: 22.4 },
          e2e_duration: { p50_ms: 19.3, p95_ms: 66.9, p99_ms: 157.5, avg_ms: 29.6 },
        }),
      });
    });

    await page.route("**/api/v1/analytics/queue-depth**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          queues: [
            {
              queue_name: "default",
              depth: 25,
              oldest_task_age_seconds: 1.2,
              timestamp: new Date().toISOString(),
            },
            {
              queue_name: "high-priority",
              depth: 4,
              oldest_task_age_seconds: 0.1,
              timestamp: new Date().toISOString(),
            },
          ],
        }),
      });
    });

    await page.route("**/api/v1/analytics/worker-utilization**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          workers: [
            {
              worker_id: "worker-01",
              hostname: "k8s-pod-1",
              active_task_count: 4,
              concurrency: 8,
              utilization_percent: 50,
            },
          ],
          average_utilization_percent: 50,
        }),
      });
    });

    await page.route("**/api/v1/analytics/status-distribution**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          distribution: [
            { status: "SUCCEEDED", count: 950, percentage: 95 },
            { status: "FAILED", count: 50, percentage: 5 },
          ],
          total_tasks: 1000,
        }),
      });
    });

    await page.route("**/api/v1/queues**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [{ queue_name: "default" }, { queue_name: "high-priority" }],
        }),
      });
    });
  });

  test("renders telemetry dashboard with latency percentiles and charts", async ({ page }) => {
    await page.goto("/metrics");

    await expect(page.getByRole("heading", { name: "Telemetry & Analytics" })).toBeVisible();
    await expect(page.getByText("Latency Percentiles (Queue Wait vs Execution)")).toBeVisible();
    await expect(page.getByText("157.5 ms")).toBeVisible(); // P99 e2e

    // Chart titles
    await expect(page.getByText("Throughput Velocity (Incoming vs Outgoing TPS)")).toBeVisible();
    await expect(page.getByText("Task Status Distribution")).toBeVisible();
    await expect(page.getByText("Queue Depth Backlog")).toBeVisible();
    await expect(page.getByText("Worker Slot Capacity Utilization")).toBeVisible();
  });
});

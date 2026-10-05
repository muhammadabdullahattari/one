import { test, expect } from "@playwright/test";
import { loginAs, getBackendCookies, submitTaskViaApi } from "./helpers";

test.describe("Phase 12.2 — Real-Time Streaming & Operations Integration", () => {
  test("submits tasks via API while Live Console is open and observes real-time push updates without refresh", async ({
    page,
  }) => {
    // 1. Log in as admin
    await loginAs(page, "admin", "adminpassword123");

    // 2. Open Live Operational Console (/live)
    await page.goto("/live");
    await expect(page.getByText("Live Operational Console")).toBeVisible();

    // Verify WebSocket status indicator shows connected or streaming
    await expect(
      page.locator("header").getByText(/Live WebSocket Stream|Polling Fallback/i)
    ).toBeVisible({ timeout: 10000 });

    // 3. Dispatch a real task directly via backend REST API while the browser page is open
    const cookies = await getBackendCookies("admin", "adminpassword123");
    const realtimeTaskType = `stream.pulse.${Date.now()}`;
    await submitTaskViaApi(cookies, {
      task_type: realtimeTaskType,
      queue: "default",
      priority: 9,
    });

    // 4. Assert that the task appears in the Live Console task list WITHOUT manual reload
    await expect(page.getByText(realtimeTaskType)).toBeVisible({
      timeout: 15000,
    });
  });

  test("manages distributed queues and inspects active worker fleet nodes", async ({
    page,
  }) => {
    await loginAs(page, "admin", "adminpassword123");

    // 1. Navigate to Queues page
    await page.goto("/queues");
    await expect(page.getByText("Queue Configuration")).toBeVisible();

    // Create a new test queue
    const uniqueQueue = `q-${Date.now().toString().slice(-6)}`;
    await page.getByRole("button", { name: /Create Queue/i }).click();
    await page.getByPlaceholder("e.g. notifications, billing").fill(uniqueQueue);
    await page.locator('form button[type="submit"]').click();

    // Verify queue card appears in roster
    await expect(page.getByText(uniqueQueue)).toBeVisible({ timeout: 10000 });

    // 2. Navigate to Worker Fleet page
    await page.goto("/workers");
    await expect(page.getByText("Worker Fleet")).toBeVisible();

    // Verify worker nodes or fleet capacity container is rendered
    await expect(page.getByText(/Refresh Fleet/i)).toBeVisible();
  });
});

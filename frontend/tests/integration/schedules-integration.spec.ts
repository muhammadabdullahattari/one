import { test, expect } from "@playwright/test";
import { loginAs, getBackendCookies, BASE_API_URL } from "./helpers";

test.describe("Phase 12.1 — Recurring Schedules Integration (Visual Builder & Trigger)", () => {
  test("creates a recurring schedule via visual modal, verifies cron calculation, and triggers immediate execution", async ({
    page,
  }) => {
    // 1. Log in as admin
    await loginAs(page, "admin", "adminpassword123");

    // 2. Navigate to Schedules page
    await page.goto("/schedules");
    await expect(page.getByRole("heading", { name: "Recurring Schedules" })).toBeVisible();

    // 3. Open Create Recurring Schedule Modal
    const createBtn = page.getByRole("button", { name: /Create Schedule/i });
    await expect(createBtn).toBeVisible();
    await createBtn.click();

    // 4. Fill in Schedule parameters
    const uniqueType = `e2e.schedule.${Date.now()}`;
    await page.getByPlaceholder("e.g. email.daily_digest or db.cleanup").fill(uniqueType);

    // Select Frequency: Daily
    const dailyBtn = page.getByRole("button", { name: /^Daily$/i });
    if (await dailyBtn.isVisible()) {
      await dailyBtn.click();
    }

    // Set JSON payload
    const payloadTextarea = page.locator("textarea");
    if (await payloadTextarea.isVisible()) {
      await payloadTextarea.fill('{"test_mode": true}');
    }

    // Submit schedule creation
    const submitBtn = page.locator('form button[type="submit"]');
    await submitBtn.click();

    // 5. Verify the new schedule appears in the schedules table
    await expect(page.getByText(uniqueType)).toBeVisible({ timeout: 10000 });

    // Verify Active badge and cron expression
    const row = page.locator("tr", { hasText: uniqueType });
    await expect(row).toContainText(/Active/i);
    await expect(row).toContainText("*");

    // 6. Trigger the schedule immediately via UI
    const triggerBtn = row.getByRole("button", { name: /Trigger Now/i });
    await expect(triggerBtn).toBeVisible();
    await triggerBtn.click();

    // Verify toast or feedback notification
    await expect(page.getByText(/triggered successfully/i)).toBeVisible({ timeout: 10000 });

    // 7. Verify via backend REST API that a task with this task_type was spawned
    const cookies = await getBackendCookies("admin", "adminpassword123");
    const tasksRes = await fetch(`${BASE_API_URL}/tasks?limit=10`, {
      headers: { Cookie: cookies },
    });
    const tasksData = await tasksRes.json();
    const matchingTask = tasksData.items.find((t: { task_type: string }) => t.task_type === uniqueType);

    expect(matchingTask).toBeDefined();
    expect(matchingTask.task_type).toBe(uniqueType);
    expect(["PENDING", "QUEUED", "RUNNING", "SUCCEEDED"]).toContain(matchingTask.status);
  });
});

import { test, expect } from "@playwright/test";
import { loginAs, getBackendCookies, BASE_API_URL } from "./helpers";

test.describe("Phase 12.1 — Dead Letter Queue (DLQ) Replay Integration", () => {
  test("inspects real DLQ tasks, triggers replay via UI, and verifies task re-queued in active queue", async ({
    page,
  }) => {
    // 1. Log in as admin
    await loginAs(page, "admin", "adminpassword123");

    // 2. Navigate to DLQ page
    await page.goto("/dlq");
    await expect(page.getByRole("heading", { name: /Dead Letter Queue/i })).toBeVisible();

    // 3. Verify DLQ table has items
    await expect(page.getByText(/Dead Tasks Total:/i)).toBeVisible({ timeout: 10000 });

    // Find the first replay button in the table
    const firstReplayBtn = page.getByRole("button", { name: /^Replay$/i }).first();
    await expect(firstReplayBtn).toBeVisible({ timeout: 10000 });

    // Grab the task ID from the row to verify later via API
    const row = page.locator("tbody tr").first();
    const taskIdLink = row.locator("a");
    const taskId = (await taskIdLink.innerText()).trim();

    // 4. Click Replay button
    await firstReplayBtn.click();

    // 5. Verify success feedback message banner appears
    await expect(
      page.getByText(/successfully replayed into active queue/i)
    ).toBeVisible({ timeout: 10000 });

    // 6. Verify via backend REST API that the task is re-queued or completed
    const cookies = await getBackendCookies("admin", "adminpassword123");
    const taskRes = await fetch(`${BASE_API_URL}/tasks/${taskId}`, {
      headers: { Cookie: cookies },
    });

    expect(taskRes.ok).toBe(true);
    const taskData = await taskRes.json();
    expect(taskData.task_id).toBe(taskId);
    // After replay, the task is no longer stuck in DEAD status; it transitions to QUEUED, RUNNING, or SUCCEEDED
    expect(["QUEUED", "RUNNING", "SUCCEEDED", "PENDING"]).toContain(taskData.status);
  });
});

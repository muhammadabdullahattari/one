import { test, expect } from "@playwright/test";
import { loginAs, getBackendCookies, getTaskViaApi } from "./helpers";

test.describe("Phase 12.1 — Task Submission & Database State Integration", () => {
  test("submits a task via UI, verifies backlog update, and asserts identical state in DB via API", async ({
    page,
  }) => {
    // 1. Log in via UI
    await loginAs(page, "admin", "adminpassword123");

    // 2. Open task submission modal on Dashboard
    const submitBtn = page.getByRole("button", { name: /Submit Task/i });
    await expect(submitBtn).toBeVisible();
    await submitBtn.click();

    // 3. Fill out the task details with a unique identifier
    const uniqueType = `e2e.pipeline.${Date.now()}`;
    await page.getByPlaceholder("e.g. email.send or reports.daily").fill(uniqueType);

    // Select Priority 7
    const priorityInput = page.locator('input[type="number"]');
    if (await priorityInput.isVisible()) {
      await priorityInput.fill("7");
    }

    // Submit form
    const modalSubmitBtn = page.locator('div[role="dialog"] button[type="submit"], form button[type="submit"]');
    await modalSubmitBtn.click();

    // 4. Verify task appears in recent executions on the dashboard
    await expect(page.getByText(uniqueType)).toBeVisible({ timeout: 10000 });

    // 5. Navigate to the Task Backlog page (/tasks) to verify virtualized table row
    await page.goto("/tasks");
    await expect(page.getByText(uniqueType)).toBeVisible({ timeout: 10000 });

    // 6. Click on the task to inspect its details
    const taskLink = page.getByRole("link", { name: uniqueType }).first();
    await expect(taskLink).toBeVisible({ timeout: 10000 });
    await taskLink.click();
    await page.waitForURL(/\/tasks\/[0-9a-fA-F-]+/, { timeout: 15000 });

    // Extract taskId from URL
    const urlParts = page.url().split("/");
    const taskId = urlParts[urlParts.length - 1];

    // Verify task details on page
    await expect(page.locator("h1")).toContainText(uniqueType);
    await expect(page.getByRole("main").getByText(/Tenant: default/i)).toBeVisible();

    // 7. Verify via direct backend REST API that the DB state matches 100%
    const cookies = await getBackendCookies("admin", "adminpassword123");
    const apiTask = await getTaskViaApi(cookies, taskId);

    expect(apiTask.task_id).toBe(taskId);
    expect(apiTask.task_type).toBe(uniqueType);
    expect(apiTask.queue).toBe("default");
    expect(apiTask.priority).toBe(7);
    expect(apiTask.tenant_id).toBe("default");
    expect(["PENDING", "QUEUED", "RUNNING", "SUCCEEDED"]).toContain(apiTask.status);
  });
});

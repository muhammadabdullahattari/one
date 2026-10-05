import { Page, expect } from "@playwright/test";

export const BASE_API_URL = "http://127.0.0.1:8000/api/v1";

/**
 * Log into the Task Engine UI using real credentials against the FastAPI backend.
 * The backend sets an HttpOnly cookie that is maintained by the browser context.
 */
export async function loginAs(
  page: Page,
  username = "admin",
  password = "adminpassword123"
) {
  await page.goto("/login");
  await page.getByPlaceholder("admin or user@domain.com").fill(username);
  await page.getByPlaceholder("••••••••••••").fill(password);
  await page.getByRole("button", { name: /Sign In/i }).click();

  // Wait for redirect to dashboard
  await page.waitForURL(/\/dashboard/, { timeout: 25000 });
  await expect(page.getByText(/Live Operational View/i)).toBeVisible({ timeout: 15000 });
}

/**
 * Directly authenticate via the backend REST API to obtain cookies for verification calls.
 */
export async function getBackendCookies(
  username = "admin",
  password = "adminpassword123"
): Promise<string> {
  const res = await fetch(`${BASE_API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!res.ok) {
    throw new Error(`Failed to login via API: ${res.status} ${res.statusText}`);
  }

  return res.headers.get("set-cookie") || "";
}

/**
 * Direct API helper to submit a task to the real backend.
 */
export async function submitTaskViaApi(
  cookie: string,
  body: {
    task_type: string;
    queue?: string;
    priority?: number;
    payload?: Record<string, unknown>;
  }
) {
  const res = await fetch(`${BASE_API_URL}/tasks`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Cookie: cookie,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(`API task creation failed: ${res.status} ${await res.text()}`);
  }

  return res.json();
}

/**
 * Direct API helper to fetch a task by ID from the real backend.
 */
export async function getTaskViaApi(cookie: string, taskId: string) {
  const res = await fetch(`${BASE_API_URL}/tasks/${taskId}`, {
    method: "GET",
    headers: {
      Cookie: cookie,
    },
  });

  if (!res.ok) {
    throw new Error(`API fetch task failed: ${res.status} ${await res.text()}`);
  }

  return res.json();
}

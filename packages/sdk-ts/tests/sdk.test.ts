import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  TaskEngine,
  TaskEngineClient,
  AsyncResult,
  AuthenticationError,
  TaskNotFoundError,
  TaskExecutionError,
  TaskCancelledError,
  TaskTimeoutError,
  TaskEngineWebSocket,
} from "../src/index.js";

describe("TaskEngineClient", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("initializes with default options", () => {
    const client = new TaskEngineClient();
    expect(client.apiUrl).toBe("http://localhost:8000");
    expect(client.tenantId).toBe("default");
    expect(client.timeoutMs).toBe(30000);
    expect(client.apiKey).toBeUndefined();
  });

  it("initializes with custom options and strips trailing slash", () => {
    const client = new TaskEngineClient({
      apiUrl: "https://api.taskengine.dev/",
      apiKey: "secret-token",
      tenantId: "acme-corp",
      timeoutMs: 15000,
    });
    expect(client.apiUrl).toBe("https://api.taskengine.dev");
    expect(client.apiKey).toBe("secret-token");
    expect(client.tenantId).toBe("acme-corp");
    expect(client.timeoutMs).toBe(15000);
  });

  it("submits task with correct headers and payload", async () => {
    const mockResponse = {
      task_id: "task-123",
      task_type: "email.send",
      queue: "default",
      priority: 5,
      status: "QUEUED",
      attempt_count: 0,
      max_attempts: 3,
      timeout_seconds: 60,
      tenant_id: "acme",
      created_at: "2026-10-07T12:00:00Z",
    };

    let capturedUrl = "";
    let capturedOptions: RequestInit | undefined;

    globalThis.fetch = vi.fn().mockImplementation(async (url, opts) => {
      capturedUrl = String(url);
      capturedOptions = opts;
      return {
        ok: true,
        status: 200,
        json: async () => mockResponse,
      } as Response;
    });

    const client = new TaskEngineClient({
      apiUrl: "http://test-host:8000",
      apiKey: "test-key",
      tenantId: "acme",
    });

    const result = await client.submitTask({
      taskType: "email.send",
      payload: { to: "user@example.com" },
      queue: "mail",
      priority: 1,
      maxAttempts: 5,
      timeoutSeconds: 120,
    });

    expect(capturedUrl).toBe("http://test-host:8000/api/v1/tasks");
    expect(capturedOptions?.method).toBe("POST");
    const headers = capturedOptions?.headers as Record<string, string>;
    expect(headers["X-API-Key"]).toBe("test-key");
    expect(headers["X-Tenant-Id"]).toBe("acme");
    expect(headers["Authorization"]).toBe("Bearer test-key");

    const sentBody = JSON.parse(capturedOptions?.body as string);
    expect(sentBody.task_type).toBe("email.send");
    expect(sentBody.payload).toEqual({ to: "user@example.com" });
    expect(sentBody.queue).toBe("mail");
    expect(sentBody.priority).toBe(1);
    expect(sentBody.max_attempts).toBe(5);
    expect(sentBody.timeout_seconds).toBe(120);

    expect(result).toBeInstanceOf(AsyncResult);
    expect(result.id).toBe("task-123");
    expect(result.state).toBe("QUEUED");
  });

  it("handles 401 authentication error", async () => {
    globalThis.fetch = vi.fn().mockImplementation(async () => {
      return {
        ok: false,
        status: 401,
        text: async () => "Unauthorized API key",
      } as Response;
    });

    const client = new TaskEngineClient();
    await expect(
      client.submitTask({ taskType: "test" })
    ).rejects.toThrow(AuthenticationError);
  });

  it("handles 404 task not found error", async () => {
    globalThis.fetch = vi.fn().mockImplementation(async () => {
      return {
        ok: false,
        status: 404,
        text: async () => "Not Found",
      } as Response;
    });

    const client = new TaskEngineClient();
    await expect(client.getTask("non-existent")).rejects.toThrow(
      TaskNotFoundError
    );
  });

  it("cancels task and fetches result", async () => {
    const mockDetail = {
      task_id: "task-456",
      task_type: "calc",
      queue: "default",
      priority: 5,
      status: "SUCCEEDED",
      attempt_count: 1,
      max_attempts: 3,
      timeout_seconds: 60,
      created_at: "2026-10-07T12:00:00Z",
      payload: { x: 2, y: 3 },
      result: 5,
    };

    globalThis.fetch = vi.fn().mockImplementation(async (url) => {
      if (String(url).includes("/retry")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ ...mockDetail, status: "QUEUED" }),
        } as Response;
      }
      return {
        ok: true,
        status: 200,
        json: async () => mockDetail,
      } as Response;
    });

    const client = new TaskEngineClient();
    const taskResult = await client.getTaskResult("task-456");
    expect(taskResult.task_id).toBe("task-456");
    expect(taskResult.status).toBe("SUCCEEDED");
    expect(taskResult.result_data).toBe(5);

    const retryRes = await client.retryTask("task-456", 10, true);
    expect(retryRes.status).toBe("QUEUED");
  });
});

describe("AsyncResult", () => {
  it("polls and returns task result on success", async () => {
    let callCount = 0;
    const mockClient = {
      getTask: vi.fn().mockImplementation(async (taskId: string) => {
        callCount++;
        return {
          task_id: taskId,
          task_type: "compute",
          queue: "default",
          priority: 5,
          status: callCount < 3 ? "RUNNING" : "SUCCEEDED",
          attempt_count: 1,
          max_attempts: 3,
          timeout_seconds: 60,
          created_at: "2026-10-07T12:00:00Z",
          payload: {},
          result: { answer: 42 },
        };
      }),
      cancelTask: vi.fn(),
    };

    const asyncRes = new AsyncResult("task-compute-1", mockClient as any);
    expect(asyncRes.ready()).toBe(false);

    const value = await asyncRes.get({ timeoutMs: 5000, intervalMs: 10 });
    expect(value).toEqual({ answer: 42 });
    expect(asyncRes.ready()).toBe(true);
    expect(asyncRes.successful()).toBe(true);
    expect(asyncRes.failed()).toBe(false);
  });

  it("throws TaskExecutionError when task fails", async () => {
    const mockClient = {
      getTask: vi.fn().mockResolvedValue({
        task_id: "task-failed",
        task_type: "compute",
        queue: "default",
        priority: 5,
        status: "FAILED",
        attempt_count: 1,
        max_attempts: 3,
        timeout_seconds: 60,
        created_at: "2026-10-07T12:00:00Z",
        payload: {},
        error: "ZeroDivisionError: division by zero",
      }),
      cancelTask: vi.fn(),
    };

    const asyncRes = new AsyncResult("task-failed", mockClient as any);
    await expect(
      asyncRes.get({ timeoutMs: 1000, intervalMs: 10 })
    ).rejects.toThrow(TaskExecutionError);
    expect(asyncRes.failed()).toBe(true);
  });

  it("throws TaskCancelledError when task is cancelled", async () => {
    const mockClient = {
      getTask: vi.fn().mockResolvedValue({
        task_id: "task-cancelled",
        task_type: "compute",
        queue: "default",
        priority: 5,
        status: "CANCELLED",
        attempt_count: 1,
        max_attempts: 3,
        timeout_seconds: 60,
        created_at: "2026-10-07T12:00:00Z",
        payload: {},
      }),
      cancelTask: vi.fn(),
    };

    const asyncRes = new AsyncResult("task-cancelled", mockClient as any);
    await expect(
      asyncRes.get({ timeoutMs: 1000, intervalMs: 10 })
    ).rejects.toThrow(TaskCancelledError);
  });

  it("throws TaskTimeoutError when polling times out", async () => {
    const mockClient = {
      getTask: vi.fn().mockResolvedValue({
        task_id: "task-slow",
        task_type: "compute",
        queue: "default",
        priority: 5,
        status: "RUNNING",
        attempt_count: 1,
        max_attempts: 3,
        timeout_seconds: 60,
        created_at: "2026-10-07T12:00:00Z",
        payload: {},
      }),
      cancelTask: vi.fn(),
    };

    const asyncRes = new AsyncResult("task-slow", mockClient as any);
    await expect(
      asyncRes.get({ timeoutMs: 50, intervalMs: 10 })
    ).rejects.toThrow(TaskTimeoutError);
  });
});

describe("TaskEngine facade", () => {
  it("instantiates and wraps client functions", async () => {
    const engine = new TaskEngine({ apiUrl: "http://localhost:9000" });
    expect(engine.apiUrl).toBe("http://localhost:9000");
    expect(engine.tenantId).toBe("default");

    const submitSpy = vi
      .spyOn(engine.client, "submitTask")
      .mockResolvedValue(new AsyncResult("task-wrap", engine.client));

    const res = await engine.submitTask({ taskType: "test.wrap" });
    expect(submitSpy).toHaveBeenCalledWith({ taskType: "test.wrap" });
    expect(res.id).toBe("task-wrap");
  });
});

describe("TaskEngineWebSocket", () => {
  it("registers listeners and emits events", () => {
    const ws = new TaskEngineWebSocket({ apiUrl: "http://localhost:8000" });
    const received: string[] = [];

    const listener = (event: any) => {
      received.push(event.data.taskId);
    };

    ws.on("task.completed", listener);
    ws.emit("task.completed", {
      type: "task.completed",
      data: { taskId: "task-event-1" },
    });

    expect(received).toEqual(["task-event-1"]);

    ws.off("task.completed", listener);
    ws.emit("task.completed", {
      type: "task.completed",
      data: { taskId: "task-event-2" },
    });

    expect(received).toEqual(["task-event-1"]);
  });
});

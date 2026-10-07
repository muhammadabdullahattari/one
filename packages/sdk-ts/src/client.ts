import {
  AuthenticationError,
  ConnectionError,
  TaskEngineError,
  TaskNotFoundError,
} from "./errors.js";
import { AsyncResult, type TaskEngineResultClient } from "./result.js";
import type {
  ListTasksOptions,
  QueueResponse,
  ScheduleCreateOptions,
  ScheduleResponse,
  TaskDetailResponse,
  TaskEngineConfig,
  TaskListResponse,
  TaskResponse,
  TaskResultResponse,
  TaskSubmitOptions,
  WorkerResponse,
} from "./types.js";

export class TaskEngineClient implements TaskEngineResultClient {
  public readonly apiUrl: string;
  public readonly apiKey?: string | undefined;
  public readonly tenantId: string;
  public readonly timeoutMs: number;

  constructor(config?: TaskEngineConfig) {
    this.apiUrl = (
      config?.apiUrl ??
      (typeof process !== "undefined"
        ? process.env?.["TASK_ENGINE_API_URL"] ??
          process.env?.["API_URL"] ??
          "http://localhost:8000"
        : "http://localhost:8000")
    ).replace(/\/$/, "");

    this.apiKey =
      config?.apiKey ??
      (typeof process !== "undefined"
        ? process.env?.["TASK_ENGINE_API_KEY"] ?? process.env?.["API_KEY"]
        : undefined);

    this.tenantId =
      config?.tenantId ??
      (typeof process !== "undefined"
        ? process.env?.["TASK_ENGINE_TENANT_ID"] ?? "default"
        : "default");

    this.timeoutMs = config?.timeoutMs ?? 30000;
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Tenant-Id": this.tenantId,
    };
    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey;
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }
    return headers;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.apiUrl}${endpoint}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    const mergedHeaders: Record<string, string> = {
      ...this.getHeaders(),
      ...((options.headers as Record<string, string>) ?? {}),
    };

    try {
      const response = await fetch(url, {
        ...options,
        headers: mergedHeaders,
        signal: controller.signal,
      });

      if (response.status === 401) {
        const text = await response.text();
        throw new AuthenticationError(`Authentication failed: ${text}`);
      }

      if (response.status === 404) {
        throw new TaskNotFoundError(`Resource not found at ${endpoint}`);
      }

      if (!response.ok) {
        const text = await response.text();
        throw new TaskEngineError(
          `Request failed with status ${response.status}: ${text}`
        );
      }

      return (await response.json()) as T;
    } catch (err: unknown) {
      if (err instanceof TaskEngineError) {
        throw err;
      }
      throw new ConnectionError(
        `Failed to connect to Task Engine at ${this.apiUrl}: ${String(err)}`
      );
    } finally {
      clearTimeout(timer);
    }
  }

  public async submitTask(options: TaskSubmitOptions): Promise<AsyncResult> {
    const body: Record<string, unknown> = {
      task_type: options.taskType,
      payload: options.payload ?? {},
      queue: options.queue ?? "default",
      priority: options.priority ?? 5,
      tenant_id: options.tenantId ?? this.tenantId,
    };

    if (options.maxAttempts !== undefined) {
      body["max_attempts"] = options.maxAttempts;
    }
    if (options.timeoutSeconds !== undefined) {
      body["timeout_seconds"] = options.timeoutSeconds;
    }
    if (options.delaySeconds !== undefined) {
      body["delay_seconds"] = options.delaySeconds;
    }
    if (options.idempotencyKey !== undefined) {
      body["idempotency_key"] = options.idempotencyKey;
    }
    if (options.metadata !== undefined) {
      body["metadata"] = options.metadata;
    }

    const data = await this.request<TaskResponse>("/api/v1/tasks", {
      method: "POST",
      body: JSON.stringify(body),
    });

    return new AsyncResult(data.task_id, this, data);
  }

  public async getTask(taskId: string): Promise<TaskDetailResponse> {
    return this.request<TaskDetailResponse>(`/api/v1/tasks/${taskId}`);
  }

  public async getTaskResult(taskId: string): Promise<TaskResultResponse> {
    const task = await this.getTask(taskId);
    return {
      task_id: task.task_id,
      status: task.status,
      result_data: task.result,
      error_message: task.error,
    };
  }

  public async cancelTask(
    taskId: string,
    reason: string = "User requested cancellation"
  ): Promise<TaskResponse> {
    const endpoint = `/api/v1/tasks/${taskId}?reason=${encodeURIComponent(
      reason
    )}`;
    return this.request<TaskResponse>(endpoint, {
      method: "DELETE",
    });
  }

  public async retryTask(
    taskId: string,
    delaySeconds: number = 0,
    resetAttempts: boolean = false
  ): Promise<TaskResponse> {
    return this.request<TaskResponse>(`/api/v1/tasks/${taskId}/retry`, {
      method: "POST",
      body: JSON.stringify({
        delay_seconds: delaySeconds,
        reset_attempts: resetAttempts,
      }),
    });
  }

  public async registerSchedule(
    options: ScheduleCreateOptions
  ): Promise<ScheduleResponse> {
    const body: Record<string, unknown> = {
      task_type: options.taskType ?? options.name,
      queue: options.queue ?? "default",
      payload: options.payload ?? {},
      timezone: options.timezone ?? "UTC",
      tenant_id: options.tenantId ?? this.tenantId,
    };

    if (options.cron) {
      body["cron"] = options.cron;
    } else if (options.intervalSeconds !== undefined) {
      body["interval_seconds"] = options.intervalSeconds;
    }

    return this.request<ScheduleResponse>("/api/v1/schedules", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  public async listTasks(
    options?: ListTasksOptions
  ): Promise<TaskListResponse> {
    const params = new URLSearchParams();
    if (options?.limit !== undefined) {
      params.set("limit", String(options.limit));
    }
    if (options?.offset !== undefined) {
      params.set("offset", String(options.offset));
    }
    if (options?.queue) {
      params.set("queue", options.queue);
    }
    if (options?.status) {
      params.set("status", options.status);
    }
    if (options?.taskType) {
      params.set("task_type", options.taskType);
    }

    const qs = params.toString();
    const endpoint = `/api/v1/tasks${qs ? `?${qs}` : ""}`;
    return this.request<TaskListResponse>(endpoint);
  }

  public async listQueues(): Promise<QueueResponse[]> {
    return this.request<QueueResponse[]>("/api/v1/queues");
  }

  public async listWorkers(): Promise<WorkerResponse[]> {
    return this.request<WorkerResponse[]>("/api/v1/workers");
  }

  public async ping(): Promise<boolean> {
    try {
      await this.request<{ status: string }>("/health/live");
      return true;
    } catch {
      return false;
    }
  }

  public async health(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>("/health/ready");
  }

  public async waitForResult(
    taskId: string,
    timeoutMs: number = 30000,
    intervalMs: number = 500
  ): Promise<unknown> {
    const result = new AsyncResult(taskId, this);
    return result.get({ timeoutMs, intervalMs });
  }
}

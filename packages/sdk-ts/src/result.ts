import {
  TaskCancelledError,
  TaskExecutionError,
  TaskTimeoutError,
} from "./errors.js";
import type { TaskDetailResponse, TaskResponse, TaskStatus } from "./types.js";

export interface TaskEngineResultClient {
  getTask(taskId: string): Promise<TaskDetailResponse>;
  cancelTask(taskId: string, reason?: string): Promise<TaskResponse>;
}

export class AsyncResult {
  public readonly taskId: string;
  private readonly client: TaskEngineResultClient;
  private data?: TaskDetailResponse | TaskResponse | undefined;

  constructor(
    taskId: string,
    client: TaskEngineResultClient,
    initialData?: TaskDetailResponse | TaskResponse | undefined
  ) {
    this.taskId = taskId;
    this.client = client;
    this.data = initialData;
  }

  public get id(): string {
    return this.taskId;
  }

  public get state(): TaskStatus {
    return (this.data?.status ?? "QUEUED") as TaskStatus;
  }

  public get status(): TaskStatus {
    return this.state;
  }

  public get result(): unknown {
    return (this.data as TaskDetailResponse | undefined)?.result;
  }

  public get error(): string | null | undefined {
    return this.data?.error;
  }

  public get info(): TaskDetailResponse | TaskResponse | undefined {
    return this.data;
  }

  public ready(): boolean {
    return ["SUCCEEDED", "FAILED", "CANCELLED", "DEAD"].includes(this.state);
  }

  public successful(): boolean {
    return this.state === "SUCCEEDED";
  }

  public failed(): boolean {
    return ["FAILED", "DEAD"].includes(this.state);
  }

  public async refresh(): Promise<TaskDetailResponse> {
    const detail = await this.client.getTask(this.taskId);
    this.data = detail;
    return detail;
  }

  public async get(options?: {
    timeoutMs?: number;
    intervalMs?: number;
  }): Promise<unknown> {
    const timeoutMs = options?.timeoutMs ?? 30000;
    const intervalMs = options?.intervalMs ?? 500;
    const startTime = Date.now();

    while (true) {
      const current = await this.refresh();
      if (this.ready()) {
        if (this.successful()) {
          return current.result;
        }
        if (this.state === "CANCELLED") {
          throw new TaskCancelledError(this.taskId);
        }
        throw new TaskExecutionError(
          current.error ?? `Task ${this.taskId} failed`,
          this.taskId
        );
      }
      if (Date.now() - startTime > timeoutMs) {
        throw new TaskTimeoutError(this.taskId, timeoutMs);
      }
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }
  }

  public async cancel(reason?: string): Promise<boolean> {
    const res = await this.client.cancelTask(this.taskId, reason);
    this.data = res;
    return res.status === "CANCELLED";
  }
}

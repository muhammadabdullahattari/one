import { TaskEngineClient } from "./client.js";
import { TaskEngineWebSocket } from "./websocket.js";
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
import type { AsyncResult } from "./result.js";

export class TaskEngine {
  public readonly client: TaskEngineClient;

  constructor(config?: TaskEngineConfig) {
    this.client = new TaskEngineClient(config);
  }

  public get apiUrl(): string {
    return this.client.apiUrl;
  }

  public get tenantId(): string {
    return this.client.tenantId;
  }

  public async submitTask(options: TaskSubmitOptions): Promise<AsyncResult> {
    return this.client.submitTask(options);
  }

  public async getTask(taskId: string): Promise<TaskDetailResponse> {
    return this.client.getTask(taskId);
  }

  public async getTaskResult(taskId: string): Promise<TaskResultResponse> {
    return this.client.getTaskResult(taskId);
  }

  public async cancelTask(
    taskId: string,
    reason?: string
  ): Promise<TaskResponse> {
    return this.client.cancelTask(taskId, reason);
  }

  public async retryTask(
    taskId: string,
    delaySeconds: number = 0,
    resetAttempts: boolean = false
  ): Promise<TaskResponse> {
    return this.client.retryTask(taskId, delaySeconds, resetAttempts);
  }

  public async registerSchedule(
    options: ScheduleCreateOptions
  ): Promise<ScheduleResponse> {
    return this.client.registerSchedule(options);
  }

  public async listTasks(
    options?: ListTasksOptions
  ): Promise<TaskListResponse> {
    return this.client.listTasks(options);
  }

  public async listQueues(): Promise<QueueResponse[]> {
    return this.client.listQueues();
  }

  public async listWorkers(): Promise<WorkerResponse[]> {
    return this.client.listWorkers();
  }

  public async ping(): Promise<boolean> {
    return this.client.ping();
  }

  public async health(): Promise<Record<string, unknown>> {
    return this.client.health();
  }

  public async waitForResult(
    taskId: string,
    timeoutMs: number = 30000,
    intervalMs: number = 500
  ): Promise<unknown> {
    return this.client.waitForResult(taskId, timeoutMs, intervalMs);
  }

  public connectWebSocket(
    channel: "tasks" | "workers" = "tasks"
  ): TaskEngineWebSocket {
    const ws = new TaskEngineWebSocket({
      apiUrl: this.apiUrl,
      channel,
    });
    ws.connect();
    return ws;
  }
}

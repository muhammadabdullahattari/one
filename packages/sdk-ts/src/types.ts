export type TaskStatus =
  | "PENDING"
  | "SCHEDULED"
  | "QUEUED"
  | "RUNNING"
  | "RETRY_WAIT"
  | "SUCCEEDED"
  | "FAILED"
  | "TIMED_OUT"
  | "CANCELLED"
  | "DEAD";

export interface TaskEngineConfig {
  apiUrl?: string | undefined;
  apiKey?: string | undefined;
  tenantId?: string | undefined;
  timeoutMs?: number | undefined;
}

export interface TaskSubmitOptions {
  taskType: string;
  payload?: Record<string, unknown> | undefined;
  queue?: string | undefined;
  priority?: number | undefined;
  maxAttempts?: number | undefined;
  timeoutSeconds?: number | undefined;
  delaySeconds?: number | undefined;
  idempotencyKey?: string | undefined;
  tenantId?: string | undefined;
  metadata?: Record<string, unknown> | undefined;
}

export interface TaskResponse {
  task_id: string;
  task_type: string;
  queue: string;
  priority: number;
  status: TaskStatus;
  attempt_count: number;
  max_attempts: number;
  timeout_seconds: number;
  idempotency_key?: string | null | undefined;
  tenant_id?: string | null | undefined;
  created_at: string;
  scheduled_at?: string | null | undefined;
  started_at?: string | null | undefined;
  finished_at?: string | null | undefined;
  result_ref?: string | null | undefined;
  error?: string | null | undefined;
}

export interface TaskDetailResponse extends TaskResponse {
  payload: Record<string, unknown>;
  result?: unknown;
  metadata?: Record<string, unknown> | null | undefined;
  worker_id?: string | null | undefined;
  lease_expires_at?: string | null | undefined;
}

export interface TaskResultResponse {
  task_id: string;
  status: TaskStatus;
  result_data?: unknown;
  error_message?: string | null | undefined;
}

export interface ScheduleCreateOptions {
  name: string;
  taskType?: string | undefined;
  cron?: string | undefined;
  intervalSeconds?: number | undefined;
  payload?: Record<string, unknown> | undefined;
  queue?: string | undefined;
  timezone?: string | undefined;
  tenantId?: string | undefined;
}

export interface ScheduleResponse {
  schedule_id: string;
  tenant_id: string;
  task_type: string;
  queue: string;
  cron?: string | null | undefined;
  interval_seconds?: number | null | undefined;
  timezone: string;
  enabled: boolean;
  next_run_at?: string | null | undefined;
  last_run_at?: string | null | undefined;
  created_at: string;
}

export interface QueueResponse {
  queue_name: string;
  broker_backend: string;
  is_paused: boolean;
  rate_limit_rps: number;
  max_retries?: number | undefined;
  depth?: number | undefined;
}

export interface WorkerResponse {
  worker_id: string;
  status: string;
  queues: string[];
  concurrency: number;
  active_tasks: number;
  last_heartbeat: string;
}

export interface ListTasksOptions {
  queue?: string | undefined;
  status?: TaskStatus | undefined;
  taskType?: string | undefined;
  limit?: number | undefined;
  offset?: number | undefined;
}

export interface TaskListResponse {
  items: TaskResponse[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface TaskEvent {
  type: string;
  data: Record<string, unknown>;
}

export type TaskEventListener = (event: TaskEvent) => void;

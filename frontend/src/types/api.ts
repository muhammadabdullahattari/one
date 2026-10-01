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

export interface Task {
  task_id: string;
  tenant_id: string;
  task_type: string;
  queue: string;
  status: TaskStatus;
  priority: number;
  attempt_count: number;
  max_attempts: number;
  timeout_seconds: number;
  idempotency_key: string | null;
  status_reason?: string | null;
  worker_id?: string | null;
  current_worker_id?: string | null;
  created_at: string;
  scheduled_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  result_ref: string | null;
  error?: string | null;
}

export interface TaskAttempt {
  attempt_id: string;
  task_id: string;
  worker_id: string;
  attempt_number: number;
  status: string;
  leased_at: string;
  lease_expires_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_class: string | null;
  error_message_redacted: string | null;
  result_ref: string | null;
}

export interface TaskEvent {
  event_id: string;
  task_id: string;
  attempt_id: string | null;
  event_type: string;
  actor_type: string;
  actor_id: string;
  event_time: string;
  metadata_json: Record<string, unknown>;
}

export interface TaskDetail extends Task {
  payload: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  lease_expires_at?: string | null;
  attempts: TaskAttempt[];
  events: TaskEvent[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface QueueItem {
  queue_name: string;
  enabled: boolean;
  default_priority: number;
  max_concurrency: number;
  rate_limit_rps: number | null;
  broker_backend: string;
  created_at: string;
  updated_at: string;
}

export interface QueueDepth {
  queue_name: string;
  depth: number;
  oldest_task_age_seconds: number | null;
}

export interface WorkerItem {
  worker_id: string;
  hostname: string;
  process_id: number;
  version: string;
  status: "active" | "draining" | "offline";
  queues: string[];
  concurrency: number;
  active_task_count: number;
  capabilities: Record<string, unknown>;
  last_heartbeat: string;
  registered_at: string;
  drained_at: string | null;
}

export interface ScheduleItem {
  schedule_id: string;
  task_type: string;
  queue: string;
  cron: string | null;
  interval_seconds: number | null;
  timezone: string;
  misfire_policy: string;
  enabled: boolean;
  payload: Record<string, unknown>;
  next_run_at: string | null;
  last_run_at: string | null;
  total_run_count: number;
  created_at: string;
  updated_at: string;
}

export interface DLQItem {
  dlq_id: string;
  task_id: string;
  final_attempt_id: string | null;
  queue?: string;
  reason: string;
  error_class: string;
  payload_ref: string | null;
  dead_at: string;
  replay_count: number;
  last_replayed_at: string | null;
}

export interface LatencyPercentiles {
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  avg_ms: number;
}

export interface LatencyData {
  queue_wait: LatencyPercentiles;
  execution_duration: LatencyPercentiles;
  e2e_duration: LatencyPercentiles;
}

export interface ThroughputPoint {
  timestamp: string;
  incoming_rate: number;
  outgoing_rate: number;
}

export interface ThroughputData {
  points: ThroughputPoint[];
  current_incoming_tps: number;
  current_outgoing_tps: number;
}

export interface StatusDistributionItem {
  status: string;
  count: number;
  percentage: number;
}

export interface StatusDistributionData {
  distribution: StatusDistributionItem[];
  total_tasks: number;
}

export interface QueueDepthPoint {
  queue_name: string;
  depth: number;
  oldest_task_age_seconds: number | null;
  timestamp: string;
}

export interface WorkerUtilizationItem {
  worker_id: string;
  hostname: string;
  active_slots: number;
  total_concurrency: number;
  utilization_percent: number;
  status: string;
}

export interface WorkerUtilizationData {
  workers: WorkerUtilizationItem[];
  average_utilization_percent: number;
}

export interface User {
  user_id: string;
  email: string;
  username: string;
  role: string;
  tenant_id: string;
  is_active: boolean;
}

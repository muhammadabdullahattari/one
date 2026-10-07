# TypeScript & Node.js SDK Reference (`@abdullah_mog/task-engine`)

The official TypeScript and Node.js client SDK for the Event-Driven Distributed Task Processing Engine. Provides full type safety, Promise-based ergonomic APIs, WebSocket real-time subscription, and universal Node.js/browser compatibility.

---

## 1. Installation

```bash
npm install @abdullah_mog/task-engine
# or
pnpm add @abdullah_mog/task-engine
# or
yarn add @abdullah_mog/task-engine
```

Requirements: Node.js >= 18 (Node.js 20+ or 22+ recommended) or modern browser / Edge runtime with native `fetch` support.

---

## 2. Quickstart

### Submitting Tasks and Awaiting Results

```typescript
import { TaskEngine } from "@abdullah_mog/task-engine";

const engine = new TaskEngine({
  apiUrl: process.env.TASK_ENGINE_API_URL || "http://localhost:8000",
  apiKey: process.env.TASK_ENGINE_API_KEY,
  tenantId: "acme-corp",
});

async function main() {
  const result = await engine.submitTask({
    taskType: "notifications.email.send",
    payload: {
      recipient: "alice@example.com",
      subject: "Welcome to Task Engine",
      body: "Hello from TypeScript!",
    },
    queue: "notifications",
    priority: 5,
    maxAttempts: 3,
    timeoutSeconds: 60,
  });

  console.log(`Submitted task: ${result.id}`);

  const output = await result.get({ timeoutMs: 30000, intervalMs: 500 });
  console.log("Task finished with result:", output);
}

main().catch(console.error);
```

### Real-Time Updates via WebSockets

```typescript
import { TaskEngineWebSocket } from "@abdullah_mog/task-engine";

const ws = new TaskEngineWebSocket({
  apiUrl: "http://localhost:8000",
  channel: "tasks",
  reconnect: true,
  maxReconnectAttempts: 10,
});

ws.on("task.completed", (event) => {
  console.log(`Task ${event.data.taskId} completed successfully:`, event.data);
});

ws.on("task.failed", (event) => {
  console.error(`Task ${event.data.taskId} failed:`, event.data.error);
});

ws.connect();
```

---

## 3. Core API Reference

### `TaskEngine` / `TaskEngineClient`

The high-level client interface for interacting with the distributed task engine.

```typescript
import { TaskEngine, TaskEngineClient } from "@abdullah_mog/task-engine";

const engine = new TaskEngine({
  apiUrl: "http://localhost:8000",
  apiKey: "secret-token",
  tenantId: "default",
  timeoutMs: 30000,
});
```

#### Configuration Options (`TaskEngineConfig`)

| Option | Type | Default | Description |
|---|---|---|---|
| `apiUrl` | `string` | `http://localhost:8000` | Base URL of the Task Engine REST API. Defaults to `TASK_ENGINE_API_URL` or `API_URL` environment variables if omitted. |
| `apiKey` | `string` | `undefined` | Optional API key / bearer token sent in `X-API-Key` and `Authorization` headers. Defaults to `TASK_ENGINE_API_KEY`. |
| `tenantId` | `string` | `default` | Tenant identifier sent in `X-Tenant-Id` header. Defaults to `TASK_ENGINE_TENANT_ID`. |
| `timeoutMs` | `number` | `30000` | HTTP request timeout in milliseconds. |

#### Methods

* `engine.submitTask(options: TaskSubmitOptions): Promise<AsyncResult>`: Dispatches a task to the queue and returns an `AsyncResult` tracker.
* `engine.getTask(taskId: string): Promise<TaskDetailResponse>`: Fetches comprehensive status, attempts, metadata, and results for a task.
* `engine.getTaskResult(taskId: string): Promise<TaskResultResponse>`: Retrieves only the status and output result data.
* `engine.cancelTask(taskId: string, reason?: string): Promise<TaskResponse>`: Requests cancellation of a pending or running task.
* `engine.retryTask(taskId: string, delaySeconds?: number, resetAttempts?: boolean): Promise<TaskResponse>`: Requeues a failed or timed out task.
* `engine.registerSchedule(options: ScheduleCreateOptions): Promise<ScheduleResponse>`: Creates a recurring cron or interval schedule.
* `engine.listTasks(options?: ListTasksOptions): Promise<TaskListResponse>`: Lists tasks with pagination and status/queue filtering.
* `engine.listQueues(): Promise<QueueResponse[]>`: Lists active queues, depth, pause status, and rate limits.
* `engine.listWorkers(): Promise<WorkerResponse[]>`: Lists registered workers, active task count, concurrency, and heartbeats.
* `engine.ping(): Promise<boolean>`: Performs lightweight liveness probe (`/health/live`).
* `engine.health(): Promise<Record<string, unknown>>`: Fetches readiness diagnostic check (`/health/ready`).
* `engine.waitForResult(taskId: string, timeoutMs?: number, intervalMs?: number): Promise<unknown>`: Helper to poll and wait directly for a task result.
* `engine.connectWebSocket(channel?: "tasks" | "workers"): TaskEngineWebSocket`: Connects to live real-time event streaming channel.

---

### `AsyncResult`

Represents an ongoing or completed task execution.

```typescript
const result = await engine.submitTask({ taskType: "compute.hash", payload: { data: "test" } });

console.log(result.id);
console.log(result.state);
console.log(result.ready());
console.log(result.successful());
console.log(result.failed());

const value = await result.get({ timeoutMs: 15000, intervalMs: 250 });
```

#### Properties and Methods

* `result.id`: The UUID of the submitted task.
* `result.state` / `result.status`: Current status string (`PENDING`, `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `TIMED_OUT`, `DEAD`).
* `result.result`: Output payload if task has completed.
* `result.error`: Error message string if task failed.
* `result.ready()`: Returns `true` if task is in terminal state (`SUCCEEDED`, `FAILED`, `CANCELLED`, `DEAD`).
* `result.successful()`: Returns `true` if state is `SUCCEEDED`.
* `result.failed()`: Returns `true` if state is `FAILED` or `DEAD`.
* `await result.refresh()`: Re-fetches current task state from the server.
* `await result.get(options?: { timeoutMs?: number, intervalMs?: number })`: Polls until the task completes, returns result, or throws on failure/timeout.
* `await result.cancel(reason?: string)`: Requests task cancellation.

---

### `TaskEngineWebSocket`

Enables reactive event-driven applications with auto-reconnecting WebSocket feeds.

```typescript
const ws = new TaskEngineWebSocket({
  apiUrl: "http://localhost:8000",
  channel: "tasks",
  reconnect: true,
  maxReconnectAttempts: 10,
  reconnectIntervalMs: 1000,
});

ws.on("task.created", (e) => console.log("Created", e));
ws.on("task.running", (e) => console.log("Running", e));
ws.on("task.completed", (e) => console.log("Completed", e));
ws.on("task.failed", (e) => console.log("Failed", e));
ws.on("*", (e) => console.log("Wildcard event", e));

ws.connect();
```

---

## 4. Error Handling

The SDK exposes specific typed exceptions for fine-grained recovery:

```typescript
import {
  TaskEngineError,
  TaskNotFoundError,
  TaskExecutionError,
  TaskTimeoutError,
  TaskCancelledError,
  AuthenticationError,
  ConnectionError,
} from "@abdullah_mog/task-engine";

try {
  const result = await engine.submitTask({ taskType: "test" });
  await result.get({ timeoutMs: 5000 });
} catch (error) {
  if (error instanceof TaskTimeoutError) {
    console.error(`Task ${error.taskId} exceeded time limit`);
  } else if (error instanceof TaskCancelledError) {
    console.warn(`Task ${error.taskId} was cancelled`);
  } else if (error instanceof TaskExecutionError) {
    console.error(`Execution error: ${error.message} (Task ID: ${error.taskId})`);
  } else if (error instanceof AuthenticationError) {
    console.error("Invalid API credentials");
  } else if (error instanceof ConnectionError) {
    console.error("Network unreachable or engine service offline");
  } else if (error instanceof TaskNotFoundError) {
    console.error("Task ID does not exist");
  } else if (error instanceof TaskEngineError) {
    console.error("General Task Engine error:", error.message);
  }
}
```

---

## 5. Dual Module Support (CJS & ESM)

`@abdullah_mog/task-engine` ships with dual exports and TypeScript `.d.ts` declaration maps:

### ECMAScript Modules (ESM)
```typescript
import { TaskEngine } from "@abdullah_mog/task-engine";
```

### CommonJS (CJS)
```javascript
const { TaskEngine } = require("@abdullah_mog/task-engine");
```

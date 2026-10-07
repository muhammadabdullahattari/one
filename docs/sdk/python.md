# Python SDK Reference (`task-engine`)

The official Python client SDK and CLI for the Event-Driven Distributed Task Processing Engine. Designed to deliver a Celery-like developer ergonomics with zero-extra-infrastructure requirements on PostgreSQL.

---

## 1. Installation

```bash
pip install task-engine
```

Compatible with Python >= 3.14.

---

## 2. 5-Minute Quickstart (SRS §18.5)

Run background tasks with zero extra infrastructure (no Redis, no RabbitMQ required).

### Step 1: Write an Application Task

Create `tasks.py`:

```python
from task_engine import TaskEngine, TaskContext

engine = TaskEngine.from_env()


@engine.task(queue="notifications", priority=3, max_retries=3)
async def send_welcome_email(payload: dict, context: TaskContext) -> dict:
    print(f"Executing task {context.task_id} with idempotency key: {context.idempotency_key}")
    return {"status": "sent", "recipient": payload["email"]}
```

### Step 2: Apply Migrations

```bash
task-engine migrate
```

### Step 3: Start the Worker

```bash
task-engine worker -A tasks --queues notifications --concurrency 4
```

### Step 4: Start the Monitoring Console

```bash
task-engine ui --port 8000
```
Open `http://localhost:3000` to inspect live workers, queues, and task status in real time.

### Step 5: Submit Tasks Programmatically

```python
from tasks import engine, send_welcome_email

# Celery-style dispatch
result = send_welcome_email.delay({"email": "alice@example.com"})
print(f"Task submitted with ID: {result.id}")

# Wait for result
output = result.get(timeout=30)
print(f"Task succeeded: {output}")
```

---

## 3. Core API Reference

### `TaskEngine`

The central facade for managing task registration, client configuration, and worker execution.

* `TaskEngine.from_env(env_file=None, direct_mode=False) -> TaskEngine`: Loads connection parameters from environment variables (`DATABASE_URL`, `API_URL`, `API_KEY`, `TENANT_ID`).
* `engine.task(name=None, queue="default", priority=5, max_retries=3, timeout_seconds=300)`: Registers a task handler.
* `engine.submit(task_or_name, payload=None, queue="default", priority=5, ...) -> AsyncResult`: Submits a task.
* `await engine.submit_async(...) -> AsyncResult`: Asynchronous task submission.
* `engine.get_task(task_id: str) -> dict`: Retrieves task state and status metadata.
* `engine.cancel_task(task_id: str, reason="...") -> dict`: Cancels a pending or queued task.
* `engine.worker(...) -> TaskEngineWorker`: Creates an in-process worker runner.

---

### `@task` Decorator

Registers synchronous or asynchronous functions with the global task registry.

```python
from task_engine import task, TaskContext


@task(name="billing.reconcile", queue="billing", priority=8, max_attempts=5)
def reconcile_ledger(payload: dict, context: TaskContext) -> dict:
    return {"reconciled": True}
```

#### Supported Handler Signatures:
1. `async def handler(payload: dict, context: TaskContext)`
2. `def handler(payload: dict, context: TaskContext)`
3. `async def handler(**kwargs)` (kwargs unpacked from payload)
4. `def handler(**kwargs)`

#### Invocation Ergonomics:
* `fn(*args, **kwargs)`: Direct local execution (ideal for unit testing).
* `fn.delay(*args, **kwargs)`: Submits task to queue using default client.
* `fn.apply_async(args=..., kwargs=..., queue=..., priority=..., delay_seconds=...)`: Full parameterized dispatch.

---

### `TaskContext`

Provides runtime metadata injected into the running task:

* `context.task_id`: Unique UUID of the executing task.
* `context.idempotency_key`: Client-supplied idempotency key.
* `context.attempt`: Current attempt number (1-based).
* `context.queue`: Queue name.
* `context.priority`: Priority level (1–10).
* `context.tenant_id`: Tenant scope.
* `context.headers`: Metadata headers dictionary.
* `context.logger`: Structured logger pre-bound with task execution context.

---

### `AsyncResult`

Represents an eventual task outcome promise:

* `result.id`: Task UUID string.
* `result.state` / `result.status`: Current status (`QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`).
* `result.ready() -> bool`: Returns `True` if task has reached a terminal state.
* `result.successful() -> bool`: Returns `True` if completed successfully.
* `result.failed() -> bool`: Returns `True` if failed or moved to dead-letter queue.
* `result.get(timeout=None, interval=0.5) -> Any`: Synchronously waits and returns output or raises `TaskExecutionError`.
* `await result.get_async(timeout=None, interval=0.5) -> Any`: Asynchronous wait coroutine.
* `result.cancel() -> bool`: Requests task cancellation.

---

## 4. CLI Command Reference (`task-engine`)

| Command | Arguments / Options | Description |
|---|---|---|
| `task-engine worker` | `-A <app>`, `-q <queues>`, `-c <concurrency>`, `-t <tenant>` | Start worker process consuming registered tasks. |
| `task-engine scheduler` | `-A <app>`, `--leader-lock-key <key>` | Start cron scheduler daemon with distributed leader election. |
| `task-engine ui` | `-h <host>`, `-p <port>` | Start API service and display dashboard console link. |
| `task-engine migrate` | `-r <revision>` | Apply database migrations against configured PostgreSQL instance. |
| `task-engine rollback` | `-s <steps>` | Roll back recent database migrations. |
| `task-engine shell` | `-A <app>` | Interactive Python shell with `TaskEngine`, `client`, and registry pre-imported. |
| `task-engine submit` | `<task_type>`, `-p <json>`, `-q <queue>`, `--priority <n>` | Submit ad hoc task from the terminal. |
| `task-engine status` | `<task_id>` | Inspect task lifecycle details and execution output. |
| `task-engine version` | None | Print current engine and SDK release version. |

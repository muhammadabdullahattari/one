# Task Engine SDK Changelog & Migration Guide

## Version 0.1.0 (Initial Release)

### Added
- **Top-level Distribution Package**: `task-engine` package with dual packaging (`task_engine` and `src`).
- **Core Engine Facade**: `TaskEngine` class supporting `.from_env()`, `.task()` decorator factory, and `.submit()`.
- **Programmatic Client**: `TaskEngineClient` with full REST API methods (`submit`, `get_task`, `get_result`, `cancel_task`, `register_schedule`, `list_tasks`, `list_queues`, `list_workers`).
- **Zero-Infra Direct Mode**: Direct database submission and inspection mode using native PostgreSQL SKIP LOCKED outbox without requiring external broker or HTTP API.
- **Celery Ergonomics**: `@task` decorator supporting `.delay(*args, **kwargs)` and `.apply_async(...)` with direct in-process callable execution for unit testing.
- **Context Injection**: `TaskContext` exposing `task_id`, `idempotency_key`, `attempt`, `queue`, `priority`, `headers`, and pre-bound structured logger.
- **Eventual Result Promise**: `AsyncResult` with synchronous `.get(timeout=...)` and asynchronous `await .get_async(timeout=...)` polling.
- **Production CLI Entrypoint**: `task-engine` command supporting `worker`, `scheduler`, `ui`, `migrate`, `rollback`, `shell`, `submit`, `status`, and `version`.
- **PEP 561 Compliance**: `task_engine/py.typed` marker file and complete static type annotations verified with `mypy`.

---

## Migration Guide

### Migrating from Celery

| Celery Concept | Task Engine SDK Equivalent |
|---|---|
| `from celery import Celery` | `from task_engine import TaskEngine` |
| `app = Celery('proj', broker='redis://...')` | `engine = TaskEngine.from_env()` (PostgreSQL native broker by default) |
| `@app.task(queue='low')` | `@engine.task(queue='low')` or `@task(queue='low')` |
| `task.delay(arg1, arg2)` | `task.delay(arg1, arg2)` |
| `task.apply_async(args=[...], queue='...')` | `task.apply_async(args=[...], queue='...')` |
| `celery -A proj worker` | `task-engine worker -A proj` |
| `celery -A proj beat` | `task-engine scheduler -A proj` |
| `celery -A proj flower` | `task-engine ui` |

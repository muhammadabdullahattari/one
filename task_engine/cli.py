from __future__ import annotations

import asyncio
import importlib
import json
from typing import Annotated, Any

import typer
import uvicorn
from src.core.config import get_settings

app = typer.Typer(
    name="task-engine",
    help="Event-Driven Distributed Task Processing Engine CLI (SRS §18 Table 19)",
    add_completion=False,
)

worker_app = typer.Typer(
    name="worker",
    help="Worker lifecycle commands",
    invoke_without_command=True,
)
scheduler_app = typer.Typer(
    name="scheduler",
    help="Scheduler daemon lifecycle commands",
    invoke_without_command=True,
)
db_app = typer.Typer(
    name="db",
    help="Database migration and maintenance commands",
)
api_app = typer.Typer(
    name="api",
    help="API server commands",
)

app.add_typer(worker_app, name="worker")
app.add_typer(scheduler_app, name="scheduler")
app.add_typer(db_app, name="db")
app.add_typer(api_app, name="api")


def _load_app_module(app_spec: str | None) -> None:
    if not app_spec:
        return
    if ":" in app_spec:
        mod_name, _ = app_spec.split(":", 1)
        importlib.import_module(mod_name)
    else:
        importlib.import_module(app_spec)


def _run_worker(
    app_module: str | None,
    worker_id: str | None,
    queues: str,
    concurrency: int | None,
    tenant_id: str | None,
    broker: str,
) -> None:
    from src.broker.registry import get_broker_adapter
    from src.worker.runtime import WorkerRuntime

    _load_app_module(app_module)
    queue_list = [q.strip() for q in queues.split(",") if q.strip()]
    broker_adapter = get_broker_adapter(broker)

    runtime = WorkerRuntime(
        worker_id=worker_id,
        queues=queue_list,
        concurrency=concurrency,
        broker_adapter=broker_adapter,
        tenant_id=tenant_id,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    typer.echo(
        f"Starting Task Engine worker {runtime.worker_id} on queues: {queue_list} (broker: {broker})"
    )
    typer.echo("Flower Operations Console: http://localhost:5555")

    try:
        loop.run_until_complete(runtime.start())
    except (KeyboardInterrupt, SystemExit):
        typer.echo("Gracefully shutting down worker...")
        loop.run_until_complete(runtime.drain())
    finally:
        loop.close()


@worker_app.callback(invoke_without_command=True)
def worker_callback(
    ctx: typer.Context,
    app_module: Annotated[
        str | None, typer.Option("--app", "-A", help="Application module to register tasks from")
    ] = None,
    worker_id: Annotated[
        str | None, typer.Option("--worker-id", "-w", help="Custom worker identifier")
    ] = None,
    queues: Annotated[
        str, typer.Option("--queues", "-q", help="Comma-separated queue list")
    ] = "default",
    concurrency: Annotated[
        int | None, typer.Option("--concurrency", "-c", help="Worker concurrency slots")
    ] = None,
    tenant_id: Annotated[
        str | None, typer.Option("--tenant-id", "-t", help="Tenant isolation scope")
    ] = "default",
    broker: Annotated[
        str, typer.Option("--broker", "-b", help="Broker adapter backend (native, redis)")
    ] = "native",
) -> None:
    if ctx.invoked_subcommand is None:
        _run_worker(
            app_module=app_module,
            worker_id=worker_id,
            queues=queues,
            concurrency=concurrency,
            tenant_id=tenant_id,
            broker=broker,
        )


@worker_app.command(name="start")
def worker_start(
    app_module: Annotated[
        str | None, typer.Option("--app", "-A", help="Application module to register tasks from")
    ] = None,
    worker_id: Annotated[
        str | None, typer.Option("--worker-id", "-w", help="Custom worker identifier")
    ] = None,
    queues: Annotated[
        str, typer.Option("--queues", "-q", help="Comma-separated queue list")
    ] = "default",
    concurrency: Annotated[
        int | None, typer.Option("--concurrency", "-c", help="Worker concurrency slots")
    ] = None,
    tenant_id: Annotated[
        str | None, typer.Option("--tenant-id", "-t", help="Tenant isolation scope")
    ] = "default",
    broker: Annotated[
        str, typer.Option("--broker", "-b", help="Broker adapter backend (native, redis)")
    ] = "native",
) -> None:
    _run_worker(
        app_module=app_module,
        worker_id=worker_id,
        queues=queues,
        concurrency=concurrency,
        tenant_id=tenant_id,
        broker=broker,
    )


def _run_scheduler(app_module: str | None, leader_lock_key: int) -> None:
    from src.scheduler.daemon import SchedulerDaemon

    _load_app_module(app_module)
    daemon = SchedulerDaemon(leader_lock_key=leader_lock_key)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    typer.echo(f"Starting Task Engine scheduler daemon (lock key: {leader_lock_key})...")
    try:
        loop.run_until_complete(daemon.run())
    except (KeyboardInterrupt, SystemExit):
        typer.echo("Stopping scheduler daemon...")
        loop.run_until_complete(daemon.stop())
    finally:
        loop.close()


@scheduler_app.callback(invoke_without_command=True)
def scheduler_callback(
    ctx: typer.Context,
    app_module: Annotated[
        str | None, typer.Option("--app", "-A", help="Application module with task definitions")
    ] = None,
    leader_lock_key: Annotated[
        int, typer.Option("--leader-lock-key", help="PostgreSQL advisory lock key for election")
    ] = 428912,
) -> None:
    if ctx.invoked_subcommand is None:
        _run_scheduler(app_module=app_module, leader_lock_key=leader_lock_key)


@scheduler_app.command(name="start")
def scheduler_start(
    app_module: Annotated[
        str | None, typer.Option("--app", "-A", help="Application module with task definitions")
    ] = None,
    leader_lock_key: Annotated[
        int, typer.Option("--leader-lock-key", help="PostgreSQL advisory lock key for election")
    ] = 428912,
) -> None:
    _run_scheduler(app_module=app_module, leader_lock_key=leader_lock_key)


@app.command(name="flower")
def flower_cmd(
    host: Annotated[str, typer.Option("--host", "-h", help="Bind network host")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p", help="Flower console port")] = 5555,
    reload: Annotated[bool, typer.Option("--reload", help="Enable live auto-reloading")] = False,
    workers: Annotated[int, typer.Option("--workers", help="Uvicorn worker count")] = 1,
) -> None:
    settings = get_settings()
    typer.echo(f"Starting Task Engine Flower Console on http://{host}:{port}")
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        log_level=settings.log_level.lower(),
    )


@app.command(name="ui")
def ui_cmd(
    host: Annotated[str, typer.Option("--host", "-h", help="Bind network host")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p", help="Console service port")] = 5555,
    reload: Annotated[bool, typer.Option("--reload", help="Enable live auto-reloading")] = False,
    workers: Annotated[int, typer.Option("--workers", help="Uvicorn worker count")] = 1,
) -> None:
    flower_cmd(host=host, port=port, reload=reload, workers=workers)


@api_app.command(name="start")
def api_start_cmd(
    host: Annotated[str, typer.Option("--host", "-h", help="Bind network host")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p", help="API service port")] = 8000,
    reload: Annotated[bool, typer.Option("--reload", help="Enable live auto-reloading")] = False,
    workers: Annotated[int, typer.Option("--workers", help="Uvicorn worker count")] = 1,
) -> None:
    settings = get_settings()
    typer.echo(f"Starting Task Engine API on http://{host}:{port}")
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        log_level=settings.log_level.lower(),
    )


@app.command(name="migrate")
def migrate_cmd(
    revision: Annotated[
        str, typer.Option("--revision", "-r", help="Target revision target")
    ] = "head",
) -> None:
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, revision)
    typer.echo(f"Database migrated successfully to: {revision}")


@db_app.command(name="migrate")
def db_migrate_cmd(
    revision: Annotated[
        str, typer.Option("--revision", "-r", help="Target revision target")
    ] = "head",
) -> None:
    migrate_cmd(revision=revision)


@app.command(name="rollback")
def rollback_cmd(
    steps: Annotated[int, typer.Option("--steps", "-s", help="Number of migrations to revert")] = 1,
) -> None:
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    command.downgrade(alembic_cfg, f"-{steps}")
    typer.echo(f"Database rolled back by {steps} revision(s).")


@db_app.command(name="rollback")
def db_rollback_cmd(
    steps: Annotated[int, typer.Option("--steps", "-s", help="Number of migrations to revert")] = 1,
) -> None:
    rollback_cmd(steps=steps)


@app.command(name="shell")
def shell_cmd(
    app_module: Annotated[
        str | None, typer.Option("--app", "-A", help="Application module to pre-import")
    ] = None,
) -> None:
    import code

    from src.domain.task_registry import global_task_registry

    from task_engine.client import TaskEngineClient
    from task_engine.context import TaskContext
    from task_engine.decorator import task
    from task_engine.engine import TaskEngine
    from task_engine.result import AsyncResult

    local_vars: dict[str, Any] = {
        "TaskEngine": TaskEngine,
        "TaskEngineClient": TaskEngineClient,
        "task": task,
        "TaskContext": TaskContext,
        "AsyncResult": AsyncResult,
        "registry": global_task_registry,
        "client": TaskEngineClient.get_default(),
    }

    if app_module:
        _load_app_module(app_module)
        if ":" in app_module:
            mod_name, _ = app_module.split(":", 1)
            local_vars["app"] = importlib.import_module(mod_name)
        else:
            local_vars["app"] = importlib.import_module(app_module)

    typer.echo("Task Engine Interactive Shell (v0.1.0)")
    typer.echo(
        "Pre-imported: TaskEngine, TaskEngineClient, client, task, TaskContext, AsyncResult, registry"
    )
    code.interact(banner="", local=local_vars)


@app.command(name="submit")
def submit_cmd(
    task_type: Annotated[str, typer.Argument(help="Task type name to submit")],
    payload: Annotated[
        str, typer.Option("--payload", "-p", help="JSON string or file path for task payload")
    ] = "{}",
    queue: Annotated[str, typer.Option("--queue", "-q", help="Target queue")] = "default",
    priority: Annotated[int, typer.Option("--priority", help="Task priority (1-10)")] = 5,
    max_attempts: Annotated[
        int | None, typer.Option("--max-attempts", help="Max retry attempts")
    ] = None,
    timeout_seconds: Annotated[
        int | None, typer.Option("--timeout", help="Execution timeout in seconds")
    ] = None,
    delay_seconds: Annotated[
        int | None, typer.Option("--delay", help="Defer execution by N seconds")
    ] = None,
    idempotency_key: Annotated[
        str | None, typer.Option("--idempotency-key", "-k", help="Idempotency key")
    ] = None,
    api_url: Annotated[str | None, typer.Option("--api-url", help="Task Engine API URL")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API authentication key")] = None,
) -> None:
    from task_engine.client import TaskEngineClient

    parsed_payload: dict[str, Any] = {}
    if payload:
        try:
            parsed_payload = json.loads(payload)
        except json.JSONDecodeError:
            with open(payload, encoding="utf-8") as f:
                parsed_payload = json.load(f)

    client = TaskEngineClient(base_url=api_url, api_key=api_key)
    result = client.submit(
        task_type=task_type,
        payload=parsed_payload,
        queue=queue,
        priority=priority,
        max_attempts=max_attempts,
        timeout_seconds=timeout_seconds,
        delay_seconds=delay_seconds,
        idempotency_key=idempotency_key,
    )
    typer.echo(f"Task submitted successfully! ID: {result.task_id} (status: {result.status})")


@app.command(name="status")
def status_cmd(
    task_id: Annotated[str, typer.Argument(help="Task UUID to query")],
    api_url: Annotated[str | None, typer.Option("--api-url", help="Task Engine API URL")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API authentication key")] = None,
) -> None:
    from task_engine.client import TaskEngineClient

    client = TaskEngineClient(base_url=api_url, api_key=api_key)
    task_info = client.get_task(task_id)
    typer.echo(json.dumps(task_info, indent=2))


@app.command(name="version")
def version_cmd() -> None:
    settings = get_settings()
    typer.echo(f"Task Engine v{settings.app_version} ({settings.app_env.value})")


if __name__ == "__main__":
    app()

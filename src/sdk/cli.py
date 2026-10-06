import asyncio
from typing import Annotated

import typer
import uvicorn

from src.core.config import get_settings

app = typer.Typer(
    name="task-engine",
    help="Event-Driven Distributed Task Processing Engine CLI",
    add_completion=False,
)

worker_app = typer.Typer(help="Worker lifecycle commands")
scheduler_app = typer.Typer(help="Scheduler daemon lifecycle commands")
db_app = typer.Typer(help="Database migration and maintenance commands")
api_app = typer.Typer(help="API server commands")

app.add_typer(worker_app, name="worker")
app.add_typer(scheduler_app, name="scheduler")
app.add_typer(db_app, name="db")
app.add_typer(api_app, name="api")


@app.command()
def version() -> None:
    """Print the current engine version."""
    settings = get_settings()
    typer.echo(f"Task Engine v{settings.app_version} ({settings.app_env.value})")


@worker_app.command(name="start")
def worker_start(
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
) -> None:
    """Start an asynchronous worker runtime process."""
    from src.worker.runtime import WorkerRuntime

    queue_list = [q.strip() for q in queues.split(",") if q.strip()]

    runtime = WorkerRuntime(
        worker_id=worker_id,
        queues=queue_list,
        concurrency=concurrency,
        tenant_id=tenant_id,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    typer.echo(f"Starting worker {runtime.worker_id} on queues: {queue_list}")
    typer.echo("Web Operations Console (Flower equivalent): http://localhost:3000")

    try:
        loop.run_until_complete(runtime.start())
    except KeyboardInterrupt, SystemExit:
        typer.echo("Gracefully shutting down worker...")
        loop.run_until_complete(runtime.drain())
    finally:
        loop.close()


@scheduler_app.command(name="start")
def scheduler_start(
    leader_lock_key: Annotated[
        int, typer.Option("--leader-lock-key", help="PostgreSQL advisory lock key for election")
    ] = 428912,
) -> None:
    """Start the distributed cron scheduler daemon."""
    from src.scheduler.daemon import SchedulerDaemon

    daemon = SchedulerDaemon(leader_lock_key=leader_lock_key)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(daemon.run())
    except KeyboardInterrupt, SystemExit:
        typer.echo("Stopping scheduler daemon...")
        loop.run_until_complete(daemon.stop())
    finally:
        loop.close()


@api_app.command(name="start")
def api_start(
    host: Annotated[str, typer.Option("--host", "-h", help="Bind network host")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p", help="Bind TCP port")] = 8000,
    reload: Annotated[bool, typer.Option("--reload", help="Enable live auto-reloading")] = False,
    workers: Annotated[int, typer.Option("--workers", help="Uvicorn worker count")] = 1,
) -> None:
    """Start the FastAPI application surface."""
    settings = get_settings()
    typer.echo(f"Starting Task Engine API on http://{host}:{port}")
    typer.echo(f"  Interactive OpenAPI / Swagger Docs: http://localhost:{port}/docs")
    typer.echo("  Web Operations Console (Flower equivalent): http://localhost:3000")
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        log_level=settings.log_level.lower(),
    )


@db_app.command(name="migrate")
def db_migrate(
    revision: Annotated[
        str, typer.Option("--revision", "-r", help="Target revision target")
    ] = "head",
) -> None:
    """Execute Alembic database migrations forward."""
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, revision)
    typer.echo(f"Database migrated successfully to: {revision}")


@db_app.command(name="rollback")
def db_rollback(
    steps: Annotated[int, typer.Option("--steps", "-s", help="Number of migrations to revert")] = 1,
) -> None:
    """Roll back the most recent database migration(s)."""
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    command.downgrade(alembic_cfg, f"-{steps}")
    typer.echo(f"Database rolled back by {steps} revision(s).")


@app.command(name="migrate")
def migrate_alias(
    revision: Annotated[
        str, typer.Option("--revision", "-r", help="Target revision target")
    ] = "head",
) -> None:
    """Execute Alembic database migrations forward (alias for 'db migrate')."""
    db_migrate(revision=revision)


@app.command(name="rollback")
def rollback_alias(
    steps: Annotated[int, typer.Option("--steps", "-s", help="Number of migrations to revert")] = 1,
) -> None:
    """Roll back the most recent database migration(s) (alias for 'db rollback')."""
    db_rollback(steps=steps)


if __name__ == "__main__":
    app()

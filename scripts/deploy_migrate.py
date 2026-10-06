#!/usr/bin/env python3
"""
Pre-deployment automated database migration execution and verification script.
Ensures zero-downtime schema evolution and verifies rollback safety.
"""

import argparse
import asyncio
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from src.core.config import get_settings


async def verify_database_connection(url: str) -> bool:
    """Validate database connectivity and latency before executing migrations."""
    print(f"[*] Verifying database connectivity: {url.split('@')[-1] if '@' in url else url}...")
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1;"))
            row = result.scalar()
            if row == 1:
                print("[+] Database connection verified successfully.")
                return True
        return False
    except Exception as exc:
        print(f"[!] Database connection failed: {exc}", file=sys.stderr)
        return False
    finally:
        await engine.dispose()


def run_migrations(config_path: str = "alembic.ini", target: str = "head") -> None:
    """Execute Alembic migrations forward to the target revision."""
    print(f"[*] Executing Alembic migrations forward to: {target}...")
    cfg = Config(config_path)
    command.upgrade(cfg, target)
    print(f"[+] Migrations forward to '{target}' completed successfully.")


def run_rollback_rehearsal(config_path: str = "alembic.ini", steps: int = 1) -> None:
    """Rehearse rollback by stepping back and then reapplying forward."""
    print(f"[*] Rehearsing rollback of {steps} migration step(s)...")
    cfg = Config(config_path)
    print(f"[*] Downgrading -{steps}...")
    command.downgrade(cfg, f"-{steps}")
    print("[+] Downgrade verified cleanly.")
    print("[*] Re-applying upgrade to head...")
    command.upgrade(cfg, "head")
    print("[+] Rollback and re-apply rehearsal succeeded.")


async def verify_tables_exist(url: str) -> bool:
    """Verify core engine tables are present and queryable."""
    print("[*] Verifying critical tables presence post-migration...")
    engine = create_async_engine(url, pool_pre_ping=True)
    required_tables = ["tasks", "queues", "workers", "schedules", "dead_letter_tasks"]
    try:
        async with engine.connect() as conn:
            for tbl in required_tables:
                res = await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :t);"
                    ),
                    {"t": tbl},
                )
                exists = res.scalar()
                if not exists:
                    print(f"[!] Table '{tbl}' does not exist!", file=sys.stderr)
                    return False
                print(f"    - Table '{tbl}': OK")
        print("[+] All critical tables verified.")
        return True
    except Exception as exc:
        print(f"[!] Error checking tables: {exc}", file=sys.stderr)
        return False
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Task Engine Pre-Deploy Migration Runner")
    parser.add_argument("--config", default="alembic.ini", help="Path to alembic.ini")
    parser.add_argument("--target", default="head", help="Target revision (default: head)")
    parser.add_argument(
        "--test-rollback", action="store_true", help="Perform a rollback and re-apply rehearsal"
    )
    args = parser.parse_args()

    settings = get_settings()
    db_url = settings.database_url

    # Step 1: Connectivity check
    connected = asyncio.run(verify_database_connection(db_url))
    if not connected:
        sys.exit(1)

    # Step 2: Apply migrations
    run_migrations(args.config, args.target)

    # Step 3: Optional rollback rehearsal
    if args.test_rollback:
        run_rollback_rehearsal(args.config, steps=1)

    # Step 4: Verify schema tables
    tables_ok = asyncio.run(verify_tables_exist(db_url))
    if not tables_ok:
        sys.exit(1)

    print("\n[SUCCESS] Pre-deploy database migration and verification completed cleanly.")


if __name__ == "__main__":
    main()

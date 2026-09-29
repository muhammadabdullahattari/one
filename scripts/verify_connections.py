import asyncio
import sys

import asyncpg
import redis.asyncio as aioredis
from src.core.config import get_settings


async def verify_postgres(db_url: str) -> bool:
    print("\n[1/2] Testing PostgreSQL / Supabase Connection...")
    raw_url = db_url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgres+asyncpg://", "postgresql://"
    )
    try:
        conn = await asyncio.wait_for(asyncpg.connect(raw_url), timeout=10.0)
        try:
            version = await conn.fetchval("SELECT version();")
            current_db = await conn.fetchval("SELECT current_database();")
            print(f"  [SUCCESS] Connected to PostgreSQL database: '{current_db}'")
            print(f"  [INFO] Version: {version[:60]}...")
            return True
        finally:
            await conn.close()
    except TimeoutError:
        print("  [FAILED] Connection timed out after 10.0s.")
        return False
    except Exception as exc:
        print(f"  [FAILED] PostgreSQL connection error: {exc}")
        return False


async def verify_redis(redis_url: str) -> bool:
    print("\n[2/2] Testing Redis Connection...")
    try:
        client = aioredis.from_url(redis_url, socket_timeout=5.0)
        try:
            pong = await asyncio.wait_for(client.ping(), timeout=5.0)
            if pong:
                info = await client.info("server")
                redis_version = info.get("redis_version", "unknown")
                print("  [SUCCESS] Redis responded with PING -> PONG.")
                print(f"  [INFO] Redis Server Version: {redis_version}")
                return True
            print("  [FAILED] Redis did not respond with PONG.")
            return False
        finally:
            await client.aclose()
    except TimeoutError:
        print("  [FAILED] Redis ping timed out after 5.0s.")
        return False
    except Exception as exc:
        print(f"  [FAILED] Redis connection error: {exc}")
        return False


async def main() -> int:
    settings = get_settings()
    print("=" * 65)
    print("Task Engine — External Services Connection Verifier")
    print(f"Environment: {settings.app_env.value}")
    print("=" * 65)
    pg_ok = await verify_postgres(settings.database_url)
    redis_ok = await verify_redis(settings.redis_url)
    print("\n" + "=" * 65)
    print("Verification Summary:")
    print(f"  PostgreSQL / Supabase: {('PASS' if pg_ok else 'FAIL')}")
    print(f"  Redis Streams:         {('PASS' if redis_ok else 'FAIL')}")
    print("=" * 65)
    if pg_ok and redis_ok:
        print("\nAll external service connections verified successfully!")
        return 0
    else:
        print("\nWarning: One or more external service connections failed.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

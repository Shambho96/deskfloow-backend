import asyncio
import sys
import time
from urllib.parse import urlparse
from sqlalchemy import text
from app.db.session import engine
from app.config import settings


def _mask_url(url_str: str) -> str:
    """Mask password in connection URL for safe logging."""
    try:
        parsed = urlparse(url_str)
        if parsed.password:
            netloc = f"{parsed.username}:***@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return parsed._replace(netloc=netloc).geturl()
    except Exception:
        pass
    return "postgresql://***"


async def check_database_connection(abort_on_fail: bool = False) -> bool:
    """Tests async database connectivity with a 'SELECT 1' ping.

    Prints a clear [SUCCESS] or [FAILED] diagnostic banner.
    """
    db_url = settings.DATABASE_URL
    host = "unknown"
    db_name = "unknown"

    try:
        parsed = urlparse(db_url)
        host = parsed.hostname or "localhost"
        db_name = parsed.path.lstrip("/") if parsed.path else "neondb"
    except Exception:
        pass

    start_time = time.perf_counter()

    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            _ = result.scalar()
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        print("\n" + "=" * 65)
        print(" [SUCCESS] Database Connection Established!")
        print(f" Database Engine : PostgreSQL (Async)")
        print(f" Database Name   : {db_name}")
        print(f" Latency         : {elapsed_ms:.1f}ms")
        print(" Status          : Database is reachable and ready.")
        print("=" * 65 + "\n")
        return True

    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        error_msg = str(exc)
        if host and host != "unknown":
            error_msg = error_msg.replace(host, "[HOST_HIDDEN]")

        print("\n" + "!" * 65)
        print(" [FAILED] Database Connection Failed!")
        print(f" Database Engine : PostgreSQL (Async)")
        print(f" Database Name   : {db_name}")
        print(f" Error           : {exc.__class__.__name__}: {error_msg}")
        print(" Status          : Could not connect to PostgreSQL.")
        print(" Check your network connection and DATABASE_URL in .env.")
        print("!" * 65 + "\n")

        if abort_on_fail:
            sys.exit(1)
        return False


def run_sync_check(abort_on_fail: bool = True) -> bool:
    """Synchronous wrapper to run check_database_connection."""
    return asyncio.run(check_database_connection(abort_on_fail=abort_on_fail))


if __name__ == "__main__":
    run_sync_check(abort_on_fail=True)

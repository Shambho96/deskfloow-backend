from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import AsyncGenerator
from app.config import settings
import os

# Resolve Database URL
db_url = settings.DATABASE_URL

# Check if testing mode override is active
if os.getenv("TESTING") == "True" or "sqlite" in db_url:
    db_url = "sqlite+aiosqlite:///:memory:"

# asyncpg compatibility: convert libpq 'sslmode=' to asyncpg 'ssl='
if "asyncpg" in db_url:
    db_url = db_url.replace("sslmode=require", "ssl=require").replace("sslmode=prefer", "ssl=prefer").replace("sslmode=disable", "ssl=disable")

engine_kwargs = {
    "echo": settings.SQL_ECHO,
    "future": True
}

if "postgresql" in db_url:
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 300,  # Refresh idle connections before Neon / cloud firewalls drop them
        "connect_args": {
            "server_settings": {
                "jit": "off",  # Disable Postgres JIT compilation overhead for fast OLTP queries
                "application_name": "deskflow_pms"
            }
        }
    })

engine = create_async_engine(db_url, **engine_kwargs)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

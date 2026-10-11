from app.core.version_check import verify_python_version

# Verify Python version on startup before initializing the application
verify_python_version(abort_on_fail=True)

import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from sqlalchemy import text
from app.config import settings
from app.routers import auth_router
from app.core.db_check import check_database_connection
from app.db.session import engine


async def _db_keepalive_worker(interval_seconds: int = 240):
    """Background worker that pings the database every 4 minutes in development mode

    to prevent Neon serverless compute instances from auto-suspending.
    """
    try:
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
            except Exception:
                pass  # Keep-alive is best-effort
    except asyncio.CancelledError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager (startup & shutdown tasks)."""
    print(f"[INFO] Starting {settings.APP_NAME} in {settings.ENVIRONMENT} mode...")
    await check_database_connection(abort_on_fail=False)

    keepalive_task = None
    if settings.ENVIRONMENT == "development":
        keepalive_task = asyncio.create_task(_db_keepalive_worker())
        print("[INFO] Dev Keep-Alive Heartbeat activated (pings every 4m to prevent Neon sleep).")

    yield

    if keepalive_task:
        keepalive_task.cancel()
        try:
            await keepalive_task
        except asyncio.CancelledError:
            pass

    print(f"[INFO] Shutting down {settings.APP_NAME}...")

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_parameters={
        "withCredentials": True,
        "requestInterceptor": "(req) => { req.credentials = 'include'; return req; }"
    },
    lifespan=lifespan
)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_response_time_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.1f}"

    # Log REST API routes with latency (GraphQL operations are logged by GraphQLLoggerExtension)
    if not request.url.path.startswith("/graphql"):
        print(f"[HTTP] {request.method} {request.url.path} -> {response.status_code} | {duration_ms:.1f}ms", flush=True)

    return response


from strawberry.fastapi import GraphQLRouter
from app.graphql.schema import schema
from app.graphql.context import get_graphql_context

# Mount GraphQL Endpoint & GraphiQL IDE
graphql_app = GraphQLRouter(schema, context_getter=get_graphql_context)

# Include Routers
app.include_router(auth_router.router)
app.include_router(graphql_app, prefix="/graphql", tags=["GraphQL IDE"])

@app.get("/", tags=["Health Check"])
async def root():
    return {
        "status": "online",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)

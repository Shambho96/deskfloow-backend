from app.core.version_check import verify_python_version

# Verify Python version on startup before initializing the application
verify_python_version(abort_on_fail=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.routers import auth_router
from app.core.db_check import check_database_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager (startup & shutdown tasks)."""
    print(f"[INFO] Starting {settings.APP_NAME} in {settings.ENVIRONMENT} mode...")
    await check_database_connection(abort_on_fail=False)
    yield
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

"""
MemoryMesh — AI Meeting Memory System
FastAPI Backend with Cognee Memory Lifecycle

Startup:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.database.connection import init_db
from backend.services.cognee_service import cognee_service
from backend.services.llm_service import get_active_provider, PROVIDER_MODELS
from backend.utils.config import settings
from backend.utils.logger import logger
from backend.api.routers import (
    auth, meetings, memory, graph, search, chat, dashboard, decisions,
    settings as settings_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MemoryMesh API v{}", settings.app_version)

    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs("data/cognee", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    await init_db()
    logger.info("Database initialized")

    await cognee_service.initialize()
    if cognee_service.is_active:
        logger.info("Cognee memory engine ready")
    else:
        logger.warning("Cognee memory engine running in SQL-only degraded mode")

    yield

    logger.info("MemoryMesh API shutting down")


app = FastAPI(
    title="MemoryMesh API",
    description="AI Meeting Memory System — Powered by Cognee",
    version=settings.app_version,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/healthz")
async def health_check():
    provider = get_active_provider()
    return {
        "status": "ok",
        "version": settings.app_version,
        "provider": provider,
        "model": PROVIDER_MODELS[provider],
    }


app.include_router(auth.router, prefix="/api")
app.include_router(meetings.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(decisions.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("Unhandled exception: %s", str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("API_PORT", os.environ.get("PORT", settings.port)))
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=port,
        reload=settings.debug,
        log_level="info",
    )

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from max_ai.core.config import get_settings
from max_ai.core.logging import setup_logging

from .routes import (
    goals,
    pms,
    roles,
    tasks,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="max-ai",
        description="Personal Life OS with AI-Powered Accountability",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(pms.router, prefix="/api/pms", tags=["PMS"])
    app.include_router(roles.router, prefix="/api/roles", tags=["Roles"])
    app.include_router(goals.router, prefix="/api/goals", tags=["Goals"])
    app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])

    @app.get("/health")
    async def health_check() -> dict:
        return {"status": "healthy"}

    return app


app = create_app()

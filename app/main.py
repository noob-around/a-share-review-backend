from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.operations import router as operations_router
from app.api.reviews import router as reviews_router
from app.config import get_settings
from app.database import init_db
from app.schemas import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.auto_create_tables:
        init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.include_router(operations_router)
    app.include_router(reviews_router)

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", app=settings.app_name, environment=settings.environment)

    return app


app = create_app()

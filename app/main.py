from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_v1_router, legacy_router
from app.core.api_versioning import ApiVersioningMiddleware
from app.core.config import settings
from app.core.observability import RequestObservabilityMiddleware
from app.routes import health_routes

_docs_habilitados = settings.ENVIRONMENT != "production"

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs" if _docs_habilitados else None,
    redoc_url="/redoc" if _docs_habilitados else None,
    openapi_url="/openapi.json" if _docs_habilitados else None,
)

app.add_middleware(RequestObservabilityMiddleware)
app.add_middleware(ApiVersioningMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "https://reservas.ejixhole.com",
        "https://ejixhole-reservas.vercel.app",
        "https://ejixhole-frontend.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "X-CSRF-Token",
        "X-Public-Client",
    ],
    expose_headers=[
        "X-API-Version",
        "Deprecation",
        "Link",
        "X-Request-ID",
    ],
)

app.include_router(health_routes.router)
app.include_router(api_v1_router)
app.include_router(legacy_router)


@app.get("/")
def home():
    return {
        "message": f"{settings.PROJECT_NAME} API - Running",
        "current_api": "/api/v1",
    }


@app.get("/status")
def status():
    return {
        "status": "online",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "api_version": "v1",
        "api_prefix": "/api/v1",
    }

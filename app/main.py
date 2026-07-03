from fastapi import FastAPI

from app.core.config import settings
from app.routes import cliente_routes

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

app.include_router(cliente_routes.router)


@app.get("/")
def home():
    return {"message": f"{settings.PROJECT_NAME} API - Running"}


@app.get("/status")
def status():
    return {"status": "online", "project": settings.PROJECT_NAME, "version": settings.VERSION}

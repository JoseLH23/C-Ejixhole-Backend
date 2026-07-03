from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)


@app.get("/")
def home():
    return {"message": f"{settings.PROJECT_NAME} API - Running"}


@app.get("/status")
def status():
    return {"status": "online", "project": settings.PROJECT_NAME, "version": settings.VERSION}

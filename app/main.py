from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routes import auth_routes, caja_routes, cliente_routes, dashboard_routes, pago_routes, publico_routes, reporte_routes, reservacion_routes, servicio_routes

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

# CORS para desarrollo: permite que el frontend interno Vite
# (localhost:5173) y el sitio público (localhost:5174 en desarrollo,
# reservas.ejixhole.com en producción) llamen a esta API desde el
# navegador. Sin esto, el navegador bloquea el preflight OPTIONS antes
# de que llegue cualquier request real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "https://reservas.ejixhole.com",
        "https://ejixhole-reservas.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cliente_routes.router)
app.include_router(reservacion_routes.router)
app.include_router(pago_routes.router)
app.include_router(servicio_routes.router)
app.include_router(auth_routes.router)
app.include_router(caja_routes.router)
app.include_router(reporte_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(publico_routes.router)


@app.get("/")
def home():
    return {"message": f"{settings.PROJECT_NAME} API - Running"}


@app.get("/status")
def status():
    return {"status": "online", "project": settings.PROJECT_NAME, "version": settings.VERSION}

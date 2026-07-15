from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routes import auth_routes, caja_routes, cliente_routes, dashboard_routes, pago_routes, publico_routes, reporte_routes, reservacion_routes, servicio_routes, usuario_routes

# ME-02 (auditoría de seguridad 13/jul/2026): Swagger/OpenAPI
# facilitan enumerar todos los endpoints reales a cualquiera que los
# encuentre — se ocultan por defecto en producción (ENVIRONMENT
# controla esto, ver app/core/config.py).
_docs_habilitados = settings.ENVIRONMENT != "production"

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs" if _docs_habilitados else None,
    redoc_url="/redoc" if _docs_habilitados else None,
    openapi_url="/openapi.json" if _docs_habilitados else None,
)

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
        # Agregado por José directamente en producción — se conserva
        # aquí para no perderlo la próxima vez que se reemplace este
        # archivo completo.
        "https://ejixhole-frontend.vercel.app",
    ],
    allow_credentials=True,
    # ME-03 (auditoría de seguridad 13/jul/2026): antes "*"/"*" — con
    # allow_credentials=True, un comodín en métodos/headers amplía la
    # superficie ante cualquier error futuro de origen. Solo lo que
    # el frontend/portal realmente usan hoy.
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    # Los flujos idempotentes de reservaciones y pagos envían este
    # header desde ambos frontends. Debe estar permitido explícitamente
    # para que el preflight CORS del navegador no bloquee la petición.
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
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
app.include_router(usuario_routes.router)


@app.get("/")
def home():
    return {"message": f"{settings.PROJECT_NAME} API - Running"}


@app.get("/status")
def status():
    return {"status": "online", "project": settings.PROJECT_NAME, "version": settings.VERSION}

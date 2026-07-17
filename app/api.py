"""Composición central de las rutas versionadas y de compatibilidad."""
from __future__ import annotations

from fastapi import APIRouter

from app.routes import auth_routes, caja_routes, cliente_routes, dashboard_routes, evento_calendario_routes, integracion_routes, pago_routes, publico_routes, reporte_routes, reservacion_routes, servicio_routes, status_api_routes, tarifa_especial_routes, usuario_routes

API_V1_PREFIX = "/api/v1"

BUSINESS_ROUTERS = (
    cliente_routes.router,
    reservacion_routes.router,
    pago_routes.router,
    servicio_routes.router,
    auth_routes.router,
    caja_routes.router,
    reporte_routes.router,
    dashboard_routes.router,
    publico_routes.router,
    usuario_routes.router,
    evento_calendario_routes.router,
    tarifa_especial_routes.router,
)

V1_ONLY_ROUTERS = (integracion_routes.router, status_api_routes.router)

LEGACY_PREFIXES = tuple(router.prefix for router in BUSINESS_ROUTERS if router.prefix)

api_v1_router = APIRouter(prefix=API_V1_PREFIX)
legacy_router = APIRouter()

for business_router in BUSINESS_ROUTERS:
    api_v1_router.include_router(business_router)
    legacy_router.include_router(business_router, deprecated=True)

for v1_router in V1_ONLY_ROUTERS:
    api_v1_router.include_router(v1_router)

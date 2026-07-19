"""Composición de extensiones pequeñas de rutas."""
from app.routes import dashboard_routes, mh_core_observability_routes

# Hereda el prefijo y la autorización administrativa del dashboard existente.
dashboard_routes.router.include_router(mh_core_observability_routes.router)

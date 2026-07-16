"""Vista agregada y sin datos personales para MH-Core."""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.dashboard_service import DashboardService


class IntegracionMhService:
    """Compone métricas ya existentes; no agrega acceso directo nuevo a tablas."""

    _TITULOS = {
        "ingresos_hoy": "Ingresos hoy",
        "ingresos_mes": "Ingresos del mes",
        "reservaciones_activas": "Reservaciones activas",
        "proximas_7_dias": "Próximas 7 días",
        "saldo_pendiente_total": "Saldo pendiente total",
        "tasa_cancelacion_mes": "Tasa de cancelación (mes)",
        "ocupacion_promedio_mes": "Ocupación promedio (mes)",
        "diferencia_caja_hoy": "Diferencia de caja (hoy)",
    }

    def __init__(self, db):
        self.dashboard = DashboardService(db)

    def resumen_operativo(self) -> dict:
        resumen = self.dashboard.resumen()
        tarjetas = {item["titulo"]: item["valor"] for item in resumen["tarjetas"]}

        faltantes = [titulo for titulo in self._TITULOS.values() if titulo not in tarjetas]
        if faltantes:
            raise RuntimeError(
                "El Dashboard no entregó todas las métricas requeridas por la integración: "
                + ", ".join(faltantes)
            )

        metricas = {
            clave: tarjetas[titulo]
            for clave, titulo in self._TITULOS.items()
        }
        return {
            "generated_at": datetime.now(timezone.utc),
            "business_date": resumen["fecha"],
            "source": "ejixhole",
            "api_version": "v1",
            "access": "read_only",
            "scope": "ejixhole:read:operations",
            "metrics": metricas,
        }

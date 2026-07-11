"""
Service de Dashboard. NO tiene Repository propio — no toca la base de
datos directamente. Solo compone ReporteService y CajaService, que ya
existen y ya están probados. Ver docs/modulos/dashboard-diseno.md
sección 0: "el Dashboard no calcula nada nuevo".

Única excepción real: sumar `sesion.diferencia` de las sesiones de
caja que ya trae `CajaService.obtener_corte_dia()`. Eso no es una
agregación nueva — `diferencia` ya la calculó `CajaService.cerrar_sesion`
por cada sesión; aquí solo se suman valores que ya existen.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Union

from app.services.caja_service import CajaService
from app.services.reporte_service import ReporteService

Numero = Union[Decimal, int, float]


class DashboardService:
    def __init__(self, db):
        self.reportes = ReporteService(db)
        self.caja = CajaService(db)

    # --- helpers ---------------------------------------------------

    @staticmethod
    def _rango_mes_anterior(hoy: date) -> tuple[date, date]:
        primer_dia_mes_actual = hoy.replace(day=1)
        ultimo_dia_mes_anterior = primer_dia_mes_actual - timedelta(days=1)
        primer_dia_mes_anterior = ultimo_dia_mes_anterior.replace(day=1)
        return primer_dia_mes_anterior, ultimo_dia_mes_anterior

    @staticmethod
    def _tarjeta(titulo: str, valor: Numero, valor_anterior: Optional[Numero] = None) -> dict:
        comparacion_porcentaje = None
        tendencia = None

        if valor_anterior is not None:
            valor_f = float(valor)
            anterior_f = float(valor_anterior)

            if anterior_f != 0:
                comparacion_porcentaje = round(((valor_f - anterior_f) / abs(anterior_f)) * 100, 2)

            if valor_f > anterior_f:
                tendencia = "up"
            elif valor_f < anterior_f:
                tendencia = "down"
            else:
                tendencia = "neutral"

        return {
            "titulo": titulo,
            "valor": valor,
            "comparacion_valor_anterior": valor_anterior,
            "comparacion_porcentaje": comparacion_porcentaje,
            "tendencia": tendencia,
        }

    # --- endpoint ----------------------------------------------------

    def resumen(self) -> dict:
        hoy = datetime.now(timezone.utc).date()
        ayer = hoy - timedelta(days=1)
        inicio_mes_anterior, fin_mes_anterior = self._rango_mes_anterior(hoy)

        # 1. Ingresos hoy vs. ayer
        ingresos_hoy = self.reportes.reporte_ingresos(periodo="hoy")["total_neto"]
        ingresos_ayer = self.reportes.reporte_ingresos(desde=ayer, hasta=ayer)["total_neto"]

        # 2. Ingresos del mes vs. mes anterior
        ingresos_mes = self.reportes.reporte_ingresos(periodo="mes")["total_neto"]
        ingresos_mes_anterior = self.reportes.reporte_ingresos(
            desde=inicio_mes_anterior, hasta=fin_mes_anterior
        )["total_neto"]

        # 3. Reservaciones activas.
        # LIMITACIÓN CONOCIDA: reporte_reservaciones_por_estado cuenta por
        # fecha_creacion, no existe (todavía) un conteo de "activas ahora
        # sin importar cuándo se crearon". Se usa periodo="anio" como la
        # mejor aproximación disponible sin inventar una query nueva —
        # correcto para un sistema que no lleva más de un año operando;
        # subestimaría el conteo si una reservación de un año anterior
        # sigue activa. Documentado en docs/modulos/dashboard-entrega-1.md.
        por_estado_anio = self.reportes.reporte_reservaciones_por_estado(periodo="anio")["por_estado"]
        reservaciones_activas = por_estado_anio.get("pendiente", 0) + por_estado_anio.get(
            "confirmada", 0
        )

        # 4. Próximas 7 días (confirmadas)
        proximas_7_dias = self.reportes.reporte_proximas_reservaciones(dias=7)["total"]

        # 5. Saldo pendiente total (snapshot, sin rango de fecha)
        saldo_pendiente_total = self.reportes.reporte_cuentas_por_cobrar()["total_pendiente"]

        # 6. Tasa de cancelación del mes vs. mes anterior
        tasa_cancelacion_mes = self.reportes.reporte_cancelaciones(periodo="mes")["tasa_cancelacion"]
        tasa_cancelacion_mes_anterior = self.reportes.reporte_cancelaciones(
            desde=inicio_mes_anterior, hasta=fin_mes_anterior
        )["tasa_cancelacion"]

        # 7. Ocupación promedio del mes (promedio de los promedios por servicio)
        items_ocupacion = self.reportes.reporte_ocupacion(periodo="mes")["items"]
        porcentajes = [
            i["porcentaje_ocupacion_promedio"]
            for i in items_ocupacion
            if i["porcentaje_ocupacion_promedio"] is not None
        ]
        ocupacion_promedio = round(sum(porcentajes) / len(porcentajes), 2) if porcentajes else 0

        # 8. Diferencia de caja de hoy: suma de `diferencia` ya calculada
        # por CajaService en cada sesión cerrada hoy (ver docstring del módulo).
        corte_hoy = self.caja.obtener_corte_dia()
        diferencia_hoy = sum(
            (s.diferencia for s in corte_hoy["sesiones"] if s.diferencia is not None),
            Decimal("0"),
        )

        # 9. Clientes nuevos del mes vs. mes anterior
        clientes_nuevos_mes = self.reportes.reporte_clientes_nuevos(periodo="mes")["total"]
        clientes_nuevos_mes_anterior = self.reportes.reporte_clientes_nuevos(
            desde=inicio_mes_anterior, hasta=fin_mes_anterior
        )["total"]

        tarjetas = [
            self._tarjeta("Ingresos hoy", ingresos_hoy, ingresos_ayer),
            self._tarjeta("Ingresos del mes", ingresos_mes, ingresos_mes_anterior),
            self._tarjeta("Reservaciones activas", reservaciones_activas),
            self._tarjeta("Próximas 7 días", proximas_7_dias),
            self._tarjeta("Saldo pendiente total", saldo_pendiente_total),
            self._tarjeta("Tasa de cancelación (mes)", tasa_cancelacion_mes, tasa_cancelacion_mes_anterior),
            self._tarjeta("Ocupación promedio (mes)", ocupacion_promedio),
            self._tarjeta("Diferencia de caja (hoy)", diferencia_hoy),
            self._tarjeta("Clientes nuevos (mes)", clientes_nuevos_mes, clientes_nuevos_mes_anterior),
        ]

        return {"fecha": hoy, "tarjetas": tarjetas}

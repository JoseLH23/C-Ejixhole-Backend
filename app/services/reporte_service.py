"""
Service de Reportes. Toda la agregación por periodo ocurre aquí, en
Python (ver docs/modulos/reportes-diseno.md sección 1).
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status

from app.models.reservacion import ESTADOS_RESERVACION
from app.repositories.reporte_repository import ReporteRepository

PERIODOS_VALIDOS = ("hoy", "semana", "mes", "anio")
AGRUPACIONES_FECHA = ("dia", "semana", "mes")
# /reportes/ingresos admite además agrupar por método de pago, que no
# es una agrupación temporal — por eso tiene su propio set válido.
AGRUPACIONES_INGRESOS = AGRUPACIONES_FECHA + ("metodo_pago",)

# Una reservación cancelada nunca representa una "venta" real: se
# excluye de rankings de servicios/clientes/ocupación. Sí se cuenta en
# reservaciones-por-estado y cancelaciones, porque ahí es el foco.
ESTADOS_NO_CANCELADOS = tuple(e for e in ESTADOS_RESERVACION if e != "cancelada")


class ReporteService:
    def __init__(self, db):
        self.repo = ReporteRepository(db)

    # --- helpers de fechas -------------------------------------------------

    def _resolver_rango(
        self, periodo: Optional[str], desde: Optional[date], hasta: Optional[date]
    ) -> tuple[date, date]:
        if periodo is not None and periodo not in PERIODOS_VALIDOS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"periodo debe ser uno de: {PERIODOS_VALIDOS}",
            )

        hoy = datetime.now(timezone.utc).date()

        if periodo == "hoy":
            return hoy, hoy
        if periodo == "semana":
            return hoy - timedelta(days=hoy.weekday()), hoy
        if periodo == "mes":
            return hoy.replace(day=1), hoy
        if periodo == "anio":
            return hoy.replace(month=1, day=1), hoy

        # Sin periodo: usa desde/hasta manuales, o default a "mes actual"
        # si no se mandó ninguno de los dos.
        if desde is None and hasta is None:
            return hoy.replace(day=1), hoy

        resultado_desde = desde or hoy.replace(day=1)
        resultado_hasta = hasta or hoy

        if resultado_desde > resultado_hasta:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'desde' no puede ser posterior a 'hasta'.",
            )

        return resultado_desde, resultado_hasta

    def _bucket(self, fecha: date, agrupar_por: str) -> str:
        if agrupar_por == "semana":
            inicio_semana = fecha - timedelta(days=fecha.weekday())
            return inicio_semana.isoformat()
        if agrupar_por == "mes":
            return fecha.strftime("%Y-%m")
        return fecha.isoformat()  # "dia"

    # --- reportes ------------------------------------------------------

    def reporte_ingresos(
        self,
        periodo: Optional[str] = None,
        desde: Optional[date] = None,
        hasta: Optional[date] = None,
        agrupar_por: str = "dia",
        metodo_pago: Optional[str] = None,
        servicio_id: Optional[int] = None,
    ) -> dict:
        if agrupar_por not in AGRUPACIONES_INGRESOS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"agrupar_por debe ser uno de: {AGRUPACIONES_INGRESOS}",
            )

        desde_resuelto, hasta_resuelto = self._resolver_rango(periodo, desde, hasta)

        pagos = self.repo.obtener_pagos(metodo_pago=metodo_pago, servicio_id=servicio_id)
        pagos_en_rango = [
            p for p in pagos if desde_resuelto <= p.fecha_pago.date() <= hasta_resuelto
        ]

        buckets: dict[str, dict[str, Decimal]] = {}
        total_ingresos = Decimal("0")
        total_reembolsos = Decimal("0")

        for p in pagos_en_rango:
            clave = p.metodo_pago if agrupar_por == "metodo_pago" else self._bucket(
                p.fecha_pago.date(), agrupar_por
            )
            if clave not in buckets:
                buckets[clave] = {"ingresos": Decimal("0"), "reembolsos": Decimal("0")}

            if p.tipo == "reembolso":
                buckets[clave]["reembolsos"] += p.monto
                total_reembolsos += p.monto
            else:
                buckets[clave]["ingresos"] += p.monto
                total_ingresos += p.monto

        serie = [
            {
                "periodo": clave,
                "ingresos": datos["ingresos"],
                "reembolsos": datos["reembolsos"],
                "neto": datos["ingresos"] - datos["reembolsos"],
            }
            for clave, datos in sorted(buckets.items())
        ]

        return {
            "desde": desde_resuelto,
            "hasta": hasta_resuelto,
            "agrupar_por": agrupar_por,
            "total_ingresos": total_ingresos,
            "total_reembolsos": total_reembolsos,
            "total_neto": total_ingresos - total_reembolsos,
            "num_pagos": len(pagos_en_rango),
            "serie": serie,
        }

    def reporte_cuentas_por_cobrar(self, antiguedad_minima_dias: Optional[int] = None) -> dict:
        if antiguedad_minima_dias is not None and antiguedad_minima_dias < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="antiguedad_minima_dias no puede ser negativo.",
            )

        reservaciones = self.repo.obtener_reservaciones_activas()
        hoy = datetime.now(timezone.utc).date()

        items = []
        total_pendiente = Decimal("0")

        for r in reservaciones:
            saldo = r.saldo_pendiente
            if saldo is None or saldo <= 0:
                continue

            antiguedad_dias = (hoy - r.fecha_creacion.date()).days
            if antiguedad_minima_dias is not None and antiguedad_dias < antiguedad_minima_dias:
                continue

            items.append(
                {
                    "reservacion_id": r.id,
                    "cliente_id": r.cliente_id,
                    "servicio_id": r.servicio_id,
                    "fecha_visita": r.fecha_visita,
                    "estado": r.estado,
                    "total": r.total,
                    "monto_pagado": r.monto_pagado,
                    "saldo_pendiente": saldo,
                    "antiguedad_dias": antiguedad_dias,
                }
            )
            total_pendiente += saldo

        items.sort(key=lambda item: item["antiguedad_dias"], reverse=True)

        return {
            "fecha_corte": hoy,
            "num_reservaciones": len(items),
            "total_pendiente": total_pendiente,
            "items": items,
        }

    def reporte_ocupacion(
        self,
        periodo: Optional[str] = None,
        desde: Optional[date] = None,
        hasta: Optional[date] = None,
        servicio_id: Optional[int] = None,
    ) -> dict:
        """
        Ocupación PROMEDIO por reservación: capacidad_maxima es un
        límite por reservación/sesión (ej. "máximo 10 personas por
        tour"), no una capacidad total del periodo. Por eso el
        porcentaje se calcula como el promedio de (num_personas /
        capacidad_maxima) entre todas las reservaciones del servicio en
        el rango — no como personas-totales / capacidad (esa cuenta no
        tendría un significado de negocio claro).
        """
        desde_r, hasta_r = self._resolver_rango(periodo, desde, hasta)

        servicios = self.repo.obtener_servicios(servicio_id=servicio_id, solo_activos=True)
        reservaciones = self.repo.obtener_reservaciones(servicio_id=servicio_id)
        relevantes = [
            r
            for r in reservaciones
            if desde_r <= r.fecha_visita <= hasta_r and r.estado in ESTADOS_NO_CANCELADOS
        ]

        items = []
        for s in servicios:
            propias = [r for r in relevantes if r.servicio_id == s.id]
            num_reservaciones = len(propias)
            total_personas = sum(r.num_personas for r in propias)
            promedio_personas = (
                round(total_personas / num_reservaciones, 2) if num_reservaciones else 0.0
            )

            porcentaje_promedio = None
            if s.capacidad_maxima and num_reservaciones:
                porcentajes = [r.num_personas / s.capacidad_maxima * 100 for r in propias]
                porcentaje_promedio = round(sum(porcentajes) / len(porcentajes), 2)

            items.append(
                {
                    "servicio_id": s.id,
                    "servicio_nombre": s.nombre,
                    "capacidad_maxima": s.capacidad_maxima,
                    "num_reservaciones": num_reservaciones,
                    "total_personas": total_personas,
                    "promedio_personas_por_reservacion": promedio_personas,
                    "porcentaje_ocupacion_promedio": porcentaje_promedio,
                }
            )

        items.sort(key=lambda item: item["num_reservaciones"], reverse=True)

        return {"desde": desde_r, "hasta": hasta_r, "items": items}

    def reporte_servicios_mas_vendidos(
        self,
        periodo: Optional[str] = None,
        desde: Optional[date] = None,
        hasta: Optional[date] = None,
        limit: int = 10,
    ) -> dict:
        desde_r, hasta_r = self._resolver_rango(periodo, desde, hasta)

        reservaciones = self.repo.obtener_reservaciones()
        relevantes = [
            r
            for r in reservaciones
            if desde_r <= r.fecha_creacion.date() <= hasta_r and r.estado in ESTADOS_NO_CANCELADOS
        ]

        agregados: dict[int, dict] = {}
        for r in relevantes:
            if r.servicio_id not in agregados:
                agregados[r.servicio_id] = {
                    "servicio_id": r.servicio_id,
                    "servicio_nombre": r.servicio.nombre,
                    "num_reservaciones": 0,
                    "total_facturado": Decimal("0"),
                }
            agregados[r.servicio_id]["num_reservaciones"] += 1
            agregados[r.servicio_id]["total_facturado"] += r.total

        items = sorted(
            agregados.values(), key=lambda item: item["num_reservaciones"], reverse=True
        )[:limit]

        return {"desde": desde_r, "hasta": hasta_r, "items": items}

    def reporte_clientes_frecuentes(
        self,
        periodo: Optional[str] = None,
        desde: Optional[date] = None,
        hasta: Optional[date] = None,
        limit: int = 10,
        minimo_reservaciones: int = 2,
    ) -> dict:
        if minimo_reservaciones < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="minimo_reservaciones debe ser al menos 1.",
            )

        desde_r, hasta_r = self._resolver_rango(periodo, desde, hasta)

        reservaciones = self.repo.obtener_reservaciones()
        relevantes = [
            r
            for r in reservaciones
            if desde_r <= r.fecha_creacion.date() <= hasta_r and r.estado in ESTADOS_NO_CANCELADOS
        ]

        agregados: dict[int, dict] = {}
        for r in relevantes:
            if r.cliente_id not in agregados:
                agregados[r.cliente_id] = {
                    "cliente_id": r.cliente_id,
                    "cliente_nombre": r.cliente.nombre,
                    "num_reservaciones": 0,
                    "total_gastado": Decimal("0"),
                }
            agregados[r.cliente_id]["num_reservaciones"] += 1
            agregados[r.cliente_id]["total_gastado"] += r.total

        items = [v for v in agregados.values() if v["num_reservaciones"] >= minimo_reservaciones]
        items.sort(key=lambda item: item["num_reservaciones"], reverse=True)
        items = items[:limit]

        return {
            "desde": desde_r,
            "hasta": hasta_r,
            "minimo_reservaciones": minimo_reservaciones,
            "items": items,
        }

    def reporte_reservaciones_por_estado(
        self,
        periodo: Optional[str] = None,
        desde: Optional[date] = None,
        hasta: Optional[date] = None,
        servicio_id: Optional[int] = None,
        origen: Optional[str] = None,
    ) -> dict:
        desde_r, hasta_r = self._resolver_rango(periodo, desde, hasta)

        reservaciones = self.repo.obtener_reservaciones(servicio_id=servicio_id, origen=origen)
        relevantes = [
            r for r in reservaciones if desde_r <= r.fecha_creacion.date() <= hasta_r
        ]

        por_estado = {estado: 0 for estado in ESTADOS_RESERVACION}
        for r in relevantes:
            por_estado[r.estado] += 1

        return {
            "desde": desde_r,
            "hasta": hasta_r,
            "total": len(relevantes),
            "por_estado": por_estado,
        }

    def reporte_cancelaciones(
        self,
        periodo: Optional[str] = None,
        desde: Optional[date] = None,
        hasta: Optional[date] = None,
    ) -> dict:
        desde_r, hasta_r = self._resolver_rango(periodo, desde, hasta)

        reservaciones = self.repo.obtener_reservaciones()
        relevantes = [
            r for r in reservaciones if desde_r <= r.fecha_creacion.date() <= hasta_r
        ]
        canceladas = [r for r in relevantes if r.estado == "cancelada"]

        total = len(relevantes)
        num_canceladas = len(canceladas)
        tasa = round((num_canceladas / total) * 100, 2) if total else 0.0

        desglose: dict[int, dict] = {}
        for r in canceladas:
            if r.servicio_id not in desglose:
                desglose[r.servicio_id] = {
                    "servicio_id": r.servicio_id,
                    "servicio_nombre": r.servicio.nombre,
                    "num_cancelaciones": 0,
                }
            desglose[r.servicio_id]["num_cancelaciones"] += 1

        desglose_ordenado = sorted(
            desglose.values(), key=lambda item: item["num_cancelaciones"], reverse=True
        )

        return {
            "desde": desde_r,
            "hasta": hasta_r,
            "total_reservaciones": total,
            "num_canceladas": num_canceladas,
            "tasa_cancelacion": tasa,
            "desglose_por_servicio": desglose_ordenado,
        }

    def reporte_tendencia_reservaciones(
        self,
        periodo: Optional[str] = None,
        desde: Optional[date] = None,
        hasta: Optional[date] = None,
        agrupar_por: str = "dia",
        estado: Optional[str] = None,
    ) -> dict:
        if agrupar_por not in AGRUPACIONES_FECHA:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"agrupar_por debe ser uno de: {AGRUPACIONES_FECHA}",
            )
        if estado is not None and estado not in ESTADOS_RESERVACION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"estado debe ser uno de: {ESTADOS_RESERVACION}",
            )

        desde_r, hasta_r = self._resolver_rango(periodo, desde, hasta)

        reservaciones = self.repo.obtener_reservaciones()
        relevantes = [
            r
            for r in reservaciones
            if desde_r <= r.fecha_creacion.date() <= hasta_r and (estado is None or r.estado == estado)
        ]

        buckets: dict[str, int] = {}
        for r in relevantes:
            clave = self._bucket(r.fecha_creacion.date(), agrupar_por)
            buckets[clave] = buckets.get(clave, 0) + 1

        serie = [
            {"periodo": clave, "num_reservaciones": total}
            for clave, total in sorted(buckets.items())
        ]

        return {
            "desde": desde_r,
            "hasta": hasta_r,
            "agrupar_por": agrupar_por,
            "total": len(relevantes),
            "serie": serie,
        }

    def reporte_clientes_nuevos(
        self,
        periodo: Optional[str] = None,
        desde: Optional[date] = None,
        hasta: Optional[date] = None,
        agrupar_por: str = "dia",
    ) -> dict:
        if agrupar_por not in AGRUPACIONES_FECHA:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"agrupar_por debe ser uno de: {AGRUPACIONES_FECHA}",
            )

        desde_r, hasta_r = self._resolver_rango(periodo, desde, hasta)

        clientes = self.repo.obtener_clientes()
        relevantes = [c for c in clientes if desde_r <= c.fecha_creacion.date() <= hasta_r]

        buckets: dict[str, int] = {}
        for c in relevantes:
            clave = self._bucket(c.fecha_creacion.date(), agrupar_por)
            buckets[clave] = buckets.get(clave, 0) + 1

        serie = [
            {"periodo": clave, "num_clientes": total} for clave, total in sorted(buckets.items())
        ]

        return {
            "desde": desde_r,
            "hasta": hasta_r,
            "agrupar_por": agrupar_por,
            "total": len(relevantes),
            "serie": serie,
        }

    def reporte_proximas_reservaciones(self, dias: int = 7, estado: Optional[str] = "confirmada") -> dict:
        if dias < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="dias debe ser al menos 1."
            )
        if estado is not None and estado not in ESTADOS_RESERVACION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"estado debe ser uno de: {ESTADOS_RESERVACION}",
            )

        hoy = datetime.now(timezone.utc).date()
        limite = hoy + timedelta(days=dias)

        reservaciones = self.repo.obtener_reservaciones()
        relevantes = [
            r
            for r in reservaciones
            if hoy <= r.fecha_visita <= limite and (estado is None or r.estado == estado)
        ]
        relevantes.sort(key=lambda r: r.fecha_visita)

        items = [
            {
                "reservacion_id": r.id,
                "cliente_id": r.cliente_id,
                "cliente_nombre": r.cliente.nombre,
                "servicio_id": r.servicio_id,
                "servicio_nombre": r.servicio.nombre,
                "fecha_visita": r.fecha_visita,
                "num_personas": r.num_personas,
                "estado": r.estado,
            }
            for r in relevantes
        ]

        return {
            "desde": hoy,
            "hasta": limite,
            "dias": dias,
            "total": len(items),
            "items": items,
        }

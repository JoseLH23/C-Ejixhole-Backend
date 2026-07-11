"""
Service de Caja. Reglas de negocio; el acceso a datos se delega a
CajaRepository.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.caja import CajaMovimiento, CajaSesion
from app.repositories.caja_repository import CajaRepository


class CajaService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CajaRepository(db)

    def abrir_sesion(self, usuario_id: int, monto_apertura: Decimal) -> CajaSesion:
        # Chequeo previo "amigable": el índice único parcial en Postgres
        # es la garantía real contra condiciones de carrera; esto solo
        # da un mensaje claro en el caso normal (sin carrera).
        abierta = self.repo.obtener_sesion_abierta_por_usuario(usuario_id)
        if abierta:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Ya tienes una sesión de caja abierta (id={abierta.id}, "
                    f"abierta desde {abierta.fecha_apertura}). Ciérrala antes de abrir otra."
                ),
            )

        sesion = CajaSesion(usuario_id=usuario_id, monto_apertura=monto_apertura, estado="abierta")

        try:
            return self.repo.crear_sesion(sesion)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una sesión de caja abierta para este usuario (detectado al guardar).",
            )

    def obtener_sesion_por_id(self, sesion_id: int) -> CajaSesion:
        sesion = self.repo.obtener_sesion_por_id(sesion_id)
        if not sesion:
            raise HTTPException(status_code=404, detail="Sesión de caja no encontrada.")
        return sesion

    def listar_sesiones(self, **filtros) -> list[CajaSesion]:
        return self.repo.listar_sesiones(**filtros)

    def registrar_movimiento(
        self, sesion_id: int, usuario_id: int, tipo: str, monto: Decimal, concepto: str
    ) -> CajaMovimiento:
        sesion = self.obtener_sesion_por_id(sesion_id)
        if sesion.estado != "abierta":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pueden registrar movimientos en una sesión de caja cerrada.",
            )

        movimiento = CajaMovimiento(
            caja_sesion_id=sesion_id,
            usuario_id=usuario_id,
            tipo=tipo,
            monto=monto,
            concepto=concepto,
        )
        return self.repo.crear_movimiento(movimiento)

    def listar_movimientos(self, sesion_id: int) -> list[CajaMovimiento]:
        self.obtener_sesion_por_id(sesion_id)  # valida que exista, lanza 404 si no
        return self.repo.listar_movimientos(sesion_id)

    def cerrar_sesion(self, sesion_id: int, monto_cierre_real: Decimal) -> CajaSesion:
        sesion = self.obtener_sesion_por_id(sesion_id)
        if sesion.estado != "abierta":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Esta sesión ya está cerrada."
            )

        monto_esperado = sesion.saldo_actual  # monto_apertura + ingresos - egresos

        sesion.monto_cierre_esperado = monto_esperado
        sesion.monto_cierre_real = monto_cierre_real
        sesion.diferencia = monto_cierre_real - monto_esperado
        sesion.estado = "cerrada"
        sesion.fecha_cierre = datetime.now(timezone.utc)

        return self.repo.guardar_sesion(sesion)

    def obtener_corte_dia(self, fecha: Optional[date] = None, usuario_id: Optional[int] = None) -> dict:
        """
        Corte de caja del día: agrega todas las sesiones cuya
        fecha_apertura cae en ese día (UTC), sumando ingresos/egresos
        de todos sus movimientos, sin importar si la sesión ya se
        cerró o sigue abierta al momento de consultar el corte.

        El filtro por fecha se hace en Python (no en la query SQL)
        para evitar comportamientos distintos entre SQLite (usado en
        los tests) y Postgres al comparar DateTime con timezone.
        """
        fecha = fecha or datetime.now(timezone.utc).date()

        todas = self.repo.listar_sesiones(usuario_id=usuario_id, limit=1000)
        sesiones = [s for s in todas if s.fecha_apertura.date() == fecha]

        total_ingresos = Decimal("0")
        total_egresos = Decimal("0")
        for sesion in sesiones:
            for m in sesion.movimientos:
                if m.tipo == "ingreso":
                    total_ingresos += m.monto
                else:
                    total_egresos += m.monto

        return {
            "fecha": fecha,
            "num_sesiones": len(sesiones),
            "total_ingresos": total_ingresos,
            "total_egresos": total_egresos,
            "saldo_neto": total_ingresos - total_egresos,
            "sesiones": sesiones,
        }

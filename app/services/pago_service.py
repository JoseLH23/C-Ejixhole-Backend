"""
Service de Pagos. Reglas de negocio; el acceso a datos de Pago se
delega a PagoRepository. La actualización de monto_pagado en
Reservacion vive aquí porque es la consecuencia directa de registrar
un pago, no una responsabilidad del repository.
"""
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.pago import Pago
from app.models.reservacion import Reservacion
from app.repositories.pago_repository import PagoRepository


class PagoService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PagoRepository(db)

    def registrar_pago(
        self,
        reservacion_id: int,
        usuario_id: int,
        monto: Decimal,
        tipo: str,
        metodo_pago: str,
        referencia: str | None,
        notas: str | None,
    ) -> Pago:
        reservacion = self.db.query(Reservacion).filter(Reservacion.id == reservacion_id).first()
        if not reservacion:
            raise HTTPException(status_code=404, detail="Reservación no encontrada.")

        if reservacion.estado == "cancelada" and tipo != "reembolso":
            raise HTTPException(
                status_code=400,
                detail="No se pueden registrar pagos nuevos sobre una reservación cancelada.",
            )

        if tipo == "reembolso":
            if monto > reservacion.monto_pagado:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"No se puede reembolsar ${monto}: solo se han pagado "
                        f"${reservacion.monto_pagado} en esta reservación."
                    ),
                )
        else:
            if monto > reservacion.saldo_pendiente:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"El monto (${monto}) excede el saldo pendiente "
                        f"(${reservacion.saldo_pendiente}) de esta reservación."
                    ),
                )

        pago = Pago(
            reservacion_id=reservacion_id,
            usuario_id=usuario_id,
            monto=monto,
            tipo=tipo,
            metodo_pago=metodo_pago,
            referencia=referencia,
            notas=notas,
        )
        self.db.add(pago)

        # monto_pagado se mantiene aquí, en la capa de servicios, no en
        # la base de datos (ver docs/schema.sql) — así se puede ajustar
        # con reglas especiales sin depender de un trigger de Postgres.
        if tipo == "reembolso":
            reservacion.monto_pagado = reservacion.monto_pagado - monto
        else:
            reservacion.monto_pagado = reservacion.monto_pagado + monto

        # Si ya se cubrió el total y la reservación seguía pendiente,
        # se confirma automáticamente.
        if reservacion.monto_pagado >= reservacion.total and reservacion.estado == "pendiente":
            reservacion.estado = "confirmada"

        self.db.commit()
        self.db.refresh(pago)
        return pago

    def obtener_por_id(self, pago_id: int) -> Pago:
        pago = self.repo.obtener_por_id(pago_id)
        if not pago:
            raise HTTPException(status_code=404, detail="Pago no encontrado.")
        return pago

    def listar_por_reservacion(self, reservacion_id: int) -> list[Pago]:
        return self.repo.listar_por_reservacion(reservacion_id)

    def listar(self, **filtros) -> list[Pago]:
        return self.repo.listar(**filtros)

"""Reglas de negocio de pagos y su integración atómica con Caja."""
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.caja import CajaMovimiento, CajaSesion
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
        # Bloquea la reservación hasta terminar para impedir cobros simultáneos
        # que juntos superen el saldo real.
        reservacion = (
            self.db.query(Reservacion)
            .filter(Reservacion.id == reservacion_id)
            .with_for_update()
            .first()
        )
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
        elif monto > reservacion.saldo_pendiente:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"El monto (${monto}) excede el saldo pendiente "
                    f"(${reservacion.saldo_pendiente}) de esta reservación."
                ),
            )

        # El efectivo debe quedar reflejado en Caja en la misma transacción.
        # Sin una caja abierta no se acepta el cobro: así nunca existe dinero
        # recibido que no aparezca en el corte.
        caja_abierta = None
        if metodo_pago == "efectivo":
            caja_abierta = (
                self.db.query(CajaSesion)
                .filter(CajaSesion.usuario_id == usuario_id, CajaSesion.estado == "abierta")
                .with_for_update()
                .first()
            )
            if not caja_abierta:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Abre una sesión de caja antes de registrar un pago o "
                        "reembolso en efectivo."
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
        self.db.flush()  # obtiene pago.id antes de crear el movimiento relacionado

        if tipo == "reembolso":
            reservacion.monto_pagado = reservacion.monto_pagado - monto
        else:
            reservacion.monto_pagado = reservacion.monto_pagado + monto

        if reservacion.monto_pagado >= reservacion.total and reservacion.estado == "pendiente":
            reservacion.estado = "confirmada"

        if caja_abierta is not None:
            es_reembolso = tipo == "reembolso"
            movimiento = CajaMovimiento(
                caja_sesion_id=caja_abierta.id,
                pago_id=pago.id,
                usuario_id=usuario_id,
                tipo="egreso" if es_reembolso else "ingreso",
                monto=monto,
                concepto=(
                    f"Reembolso reservación #{reservacion_id}"
                    if es_reembolso
                    else f"Pago reservación #{reservacion_id}"
                ),
            )
            self.db.add(movimiento)

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

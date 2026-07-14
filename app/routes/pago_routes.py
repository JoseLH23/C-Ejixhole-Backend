"""
Rutas de Pagos. Protegidas con JWT + rol: admin y cajero únicamente.

AL-01 (auditoría de seguridad 13/jul/2026): usuario_id YA NO se toma
del body — el mismo fix que ya se hizo en reservaciones, se había
quedado pendiente aquí. Se deriva del JWT real, no lo manda el cliente.

AL-04: protegido con Idempotency-Key real contra doble clic/reintento.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.idempotency import ejecutar_con_idempotencia
from app.database import get_db
from app.dependencies import require_roles
from app.models.usuario import Usuario
from app.schemas.pago import PagoCreate, PagoOut
from app.services.pago_service import PagoService

router = APIRouter(
    prefix="/pagos", tags=["Pagos"], dependencies=[Depends(require_roles("admin", "cajero"))]
)


@router.post("", response_model=PagoOut, status_code=201)
def registrar_pago(
    data: PagoCreate,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(require_roles("admin", "cajero")),
):
    service = PagoService(db)
    return ejecutar_con_idempotencia(
        db,
        request,
        endpoint="registrar_pago",
        cuerpo=data,
        operacion=lambda: service.registrar_pago(
            reservacion_id=data.reservacion_id,
            usuario_id=usuario_actual.id,
            monto=data.monto,
            tipo=data.tipo,
            metodo_pago=data.metodo_pago,
            referencia=data.referencia,
            notas=data.notas,
        ),
        schema_salida=PagoOut,
    )


@router.get("", response_model=list[PagoOut])
def listar_pagos(
    reservacion_id: Optional[int] = None,
    tipo: Optional[str] = None,
    metodo_pago: Optional[str] = None,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    service = PagoService(db)
    return service.listar(
        reservacion_id=reservacion_id,
        tipo=tipo,
        metodo_pago=metodo_pago,
        limit=limit,
        offset=offset,
    )


@router.get("/{pago_id}", response_model=PagoOut)
def obtener_pago(pago_id: int, db: Session = Depends(get_db)):
    service = PagoService(db)
    return service.obtener_por_id(pago_id)


@router.get("/reservacion/{reservacion_id}", response_model=list[PagoOut])
def listar_pagos_de_reservacion(reservacion_id: int, db: Session = Depends(get_db)):
    """Historial de pagos de una reservación específica, en orden cronológico."""
    service = PagoService(db)
    return service.listar_por_reservacion(reservacion_id)

"""
Rutas de Pagos. Protegidas con JWT + rol: admin y cajero únicamente
(ver docs/modulos/permisos-por-rol.md). usuario_id se sigue mandando
explícito en el body — ver nota en reservacion_routes.py.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.pago import PagoCreate, PagoOut
from app.services.pago_service import PagoService

router = APIRouter(
    prefix="/pagos", tags=["Pagos"], dependencies=[Depends(require_roles("admin", "cajero"))]
)


@router.post("", response_model=PagoOut, status_code=201)
def registrar_pago(data: PagoCreate, db: Session = Depends(get_db)):
    service = PagoService(db)
    return service.registrar_pago(
        reservacion_id=data.reservacion_id,
        usuario_id=data.usuario_id,
        monto=data.monto,
        tipo=data.tipo,
        metodo_pago=data.metodo_pago,
        referencia=data.referencia,
        notas=data.notas,
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

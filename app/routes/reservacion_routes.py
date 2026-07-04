"""
Rutas de Reservaciones. Sin autenticación por ahora, igual que
Clientes (el módulo Auth/Usuarios todavía no existe). El creador de
la reservación (usuario_id) se manda explícito en el body mientras
tanto — ver nota en app/schemas/reservacion.py.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.reservacion import ReservacionCreate, ReservacionEstadoUpdate, ReservacionOut
from app.services.reservacion_service import ReservacionService

router = APIRouter(prefix="/reservaciones", tags=["Reservaciones"])


@router.post("", response_model=ReservacionOut, status_code=201)
def crear_reservacion(data: ReservacionCreate, db: Session = Depends(get_db)):
    service = ReservacionService(db)
    return service.crear(
        cliente_id=data.cliente_id,
        servicio_id=data.servicio_id,
        usuario_id=data.usuario_id,
        fecha_visita=data.fecha_visita,
        num_personas=data.num_personas,
        origen=data.origen,
        notas=data.notas,
    )


@router.get("", response_model=list[ReservacionOut])
def listar_reservaciones(
    cliente_id: Optional[int] = None,
    servicio_id: Optional[int] = None,
    estado: Optional[str] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    service = ReservacionService(db)
    return service.listar(
        cliente_id=cliente_id,
        servicio_id=servicio_id,
        estado=estado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        limit=limit,
        offset=offset,
    )


@router.get("/{reservacion_id}", response_model=ReservacionOut)
def obtener_reservacion(reservacion_id: int, db: Session = Depends(get_db)):
    service = ReservacionService(db)
    return service.obtener_por_id(reservacion_id)


@router.patch("/{reservacion_id}/estado", response_model=ReservacionOut)
def cambiar_estado_reservacion(
    reservacion_id: int, data: ReservacionEstadoUpdate, db: Session = Depends(get_db)
):
    service = ReservacionService(db)
    return service.cambiar_estado(reservacion_id, data.nuevo_estado)

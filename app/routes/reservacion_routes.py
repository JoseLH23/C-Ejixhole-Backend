"""
Rutas de Reservaciones. Protegidas con JWT + rol: admin y operador
únicamente.

AL-01 (auditoría de seguridad 13/jul/2026): usuario_id YA NO se toma
del body — un cliente podía mandar cualquier id y atribuirle la
reservación a otra persona. Se deriva siempre de request.usuario_actual
(el usuario real autenticado por el JWT), imposible de falsear desde
el cliente.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models.usuario import Usuario
from app.schemas.reservacion import ReservacionCreate, ReservacionEstadoUpdate, ReservacionOut, ReservacionUpdate
from app.services.reservacion_service import ReservacionService

router = APIRouter(
    prefix="/reservaciones",
    tags=["Reservaciones"],
    dependencies=[Depends(require_roles("admin", "operador"))],
)


@router.post("", response_model=ReservacionOut, status_code=201)
def crear_reservacion(
    data: ReservacionCreate,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(require_roles("admin", "operador")),
):
    service = ReservacionService(db)
    return service.crear(
        cliente_id=data.cliente_id,
        servicio_id=data.servicio_id,
        usuario_id=usuario_actual.id,
        tipo_reservacion=data.tipo_reservacion,
        fecha_llegada=data.fecha_llegada,
        fecha_salida=data.fecha_salida,
        unidad_hospedaje_id=data.unidad_hospedaje_id,
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
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
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


@router.put("/{reservacion_id}", response_model=ReservacionOut)
def actualizar_reservacion(reservacion_id: int, data: ReservacionUpdate, db: Session = Depends(get_db)):
    """Edita fechas, personas, servicio y/o notas — no el tipo_reservacion
    ni el estado (para eso sigue existiendo PATCH /{id}/estado)."""
    service = ReservacionService(db)
    return service.actualizar(reservacion_id, **data.model_dump(exclude_unset=True))


@router.patch("/{reservacion_id}/estado", response_model=ReservacionOut)
def cambiar_estado_reservacion(
    reservacion_id: int, data: ReservacionEstadoUpdate, db: Session = Depends(get_db)
):
    service = ReservacionService(db)
    return service.cambiar_estado(reservacion_id, data.nuevo_estado)

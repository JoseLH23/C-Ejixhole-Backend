"""
Rutas de Reservaciones. Protegidas con JWT + rol: admin y operador únicamente.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.idempotency import ejecutar_con_idempotencia
from app.database import get_db
from app.dependencies import require_roles
from app.models.usuario import Usuario
from app.schemas.reservacion import ReservacionCreate, ReservacionEstadoUpdate, ReservacionOut, ReservacionUpdate
from app.services.bloqueo_operativo_service import BloqueoOperativoService
from app.services.reservacion_service import ReservacionService

router = APIRouter(
    prefix="/reservaciones",
    tags=["Reservaciones"],
    dependencies=[Depends(require_roles("admin", "operador"))],
)


@router.post("", response_model=ReservacionOut, status_code=201)
def crear_reservacion(
    data: ReservacionCreate,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(require_roles("admin", "operador")),
):
    BloqueoOperativoService(db).validar_disponibilidad(
        data.fecha_llegada,
        data.fecha_salida,
        data.tipo_reservacion,
        data.unidad_hospedaje_id,
    )
    service = ReservacionService(db)
    return ejecutar_con_idempotencia(
        db,
        request,
        endpoint="crear_reservacion",
        cuerpo=data,
        operacion=lambda: service.crear(
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
        ),
        schema_salida=ReservacionOut,
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
    return ReservacionService(db).listar(
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
    return ReservacionService(db).obtener_por_id(reservacion_id)


@router.put("/{reservacion_id}", response_model=ReservacionOut)
def actualizar_reservacion(reservacion_id: int, data: ReservacionUpdate, db: Session = Depends(get_db)):
    service = ReservacionService(db)
    actual = service.obtener_por_id(reservacion_id)
    nueva_llegada = data.fecha_llegada if data.fecha_llegada is not None else actual.fecha_llegada
    nueva_salida = data.fecha_salida if data.fecha_salida is not None else actual.fecha_salida
    nueva_unidad_id = (
        data.unidad_hospedaje_id
        if data.unidad_hospedaje_id is not None
        else actual.unidad_hospedaje_id
    )
    BloqueoOperativoService(db).validar_disponibilidad(
        nueva_llegada,
        nueva_salida,
        actual.tipo_reservacion,
        nueva_unidad_id,
    )
    return service.actualizar(reservacion_id, **data.model_dump(exclude_unset=True))


@router.patch("/{reservacion_id}/estado", response_model=ReservacionOut)
def cambiar_estado_reservacion(
    reservacion_id: int, data: ReservacionEstadoUpdate, db: Session = Depends(get_db)
):
    return ReservacionService(db).cambiar_estado(reservacion_id, data.nuevo_estado)

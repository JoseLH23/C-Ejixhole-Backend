"""Rutas públicas del portal de reservaciones."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.idempotency import ejecutar_con_idempotencia
from app.core.rate_limiter import limitar_publico
from app.database import get_db
from app.schemas.publico import (
    CotizacionOut,
    DisponibilidadOut,
    FechaBloqueadaPublicaOut,
    ReservacionPublicaCreate,
    ReservacionPublicaOut,
    ServicioPublicoOut,
    UnidadHospedajePublicoOut,
)
from app.services.bloqueo_operativo_service import BloqueoOperativoService
from app.services.publico_service import PublicoService

router = APIRouter(prefix="/publico", tags=["Portal público"], dependencies=[Depends(limitar_publico)])


@router.get("/servicios", response_model=list[ServicioPublicoOut])
def listar_servicios_informativos(db: Session = Depends(get_db)):
    return PublicoService(db).listar_servicios_informativos()


@router.get("/unidades-hospedaje", response_model=list[UnidadHospedajePublicoOut])
def listar_unidades_hospedaje(db: Session = Depends(get_db)):
    return PublicoService(db).listar_unidades_hospedaje()


@router.get("/fechas-bloqueadas", response_model=list[FechaBloqueadaPublicaOut])
def listar_fechas_bloqueadas(
    desde: date = Query(...),
    hasta: date = Query(...),
    db: Session = Depends(get_db),
):
    """Publica solo cierres globales; los cierres de una unidad no se
    presentan como cierre completo del parque."""
    if hasta < desde:
        raise HTTPException(status_code=400, detail="hasta no puede ser anterior a desde")
    if (hasta - desde).days > 366:
        raise HTTPException(status_code=400, detail="El rango máximo permitido es de 366 días")
    return BloqueoOperativoService(db).listar_bloqueos(desde, hasta)


@router.get("/disponibilidad", response_model=DisponibilidadOut)
def verificar_disponibilidad(
    unidad_hospedaje_id: int = Query(...),
    fecha_llegada: date = Query(...),
    fecha_salida: date = Query(...),
    db: Session = Depends(get_db),
):
    if not BloqueoOperativoService(db).hay_disponibilidad(
        fecha_llegada,
        fecha_salida,
        "hospedaje",
        unidad_hospedaje_id,
    ):
        return {"disponible": False}
    disponible = PublicoService(db).hay_disponibilidad(
        unidad_hospedaje_id,
        fecha_llegada,
        fecha_salida,
    )
    return {"disponible": disponible}


@router.get("/cotizar", response_model=CotizacionOut)
def cotizar_reservacion(
    tipo_reservacion: str = Query(...),
    fecha_llegada: date = Query(...),
    fecha_salida: date = Query(...),
    num_personas: int = Query(..., gt=0),
    unidad_hospedaje_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    BloqueoOperativoService(db).validar_disponibilidad(
        fecha_llegada,
        fecha_salida,
        tipo_reservacion,
        unidad_hospedaje_id,
    )
    noches, total, desglose = PublicoService(db).cotizar(
        tipo_reservacion=tipo_reservacion,
        fecha_llegada=fecha_llegada,
        fecha_salida=fecha_salida,
        num_personas=num_personas,
        unidad_hospedaje_id=unidad_hospedaje_id,
    )
    return {"noches": noches, "total": total, "desglose": desglose}


@router.post("/reservaciones", response_model=ReservacionPublicaOut, status_code=201)
def crear_solicitud_reservacion(
    data: ReservacionPublicaCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    BloqueoOperativoService(db).validar_disponibilidad(
        data.fecha_llegada,
        data.fecha_salida,
        data.tipo_reservacion,
        data.unidad_hospedaje_id,
    )
    servicio = PublicoService(db)
    return ejecutar_con_idempotencia(
        db,
        request,
        endpoint="publico_crear_reservacion",
        cuerpo=data,
        operacion=lambda: servicio.crear_solicitud_reservacion(
            nombre_completo=data.nombre_completo,
            email=data.email,
            telefono=data.telefono,
            tipo_reservacion=data.tipo_reservacion,
            fecha_llegada=data.fecha_llegada,
            fecha_salida=data.fecha_salida,
            num_personas=data.num_personas,
            unidad_hospedaje_id=data.unidad_hospedaje_id,
            notas=data.notas,
        ),
        schema_salida=ReservacionPublicaOut,
    )

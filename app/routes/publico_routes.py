"""
Rutas públicas — SIN autenticación. Son las únicas de todo el backend
sin JWT/rol requerido, a propósito: las usa el sitio web público que
verán los visitantes, no el personal interno.

AL-03 (auditoría de seguridad 13/jul/2026): al ser públicas por
diseño, no tenían ningún límite contra abuso automatizado — un bot
podía golpear /publico/reservaciones en bucle. Rate limiting real por
IP aplicado a nivel router.

Ver docs/portal-publico-fase-2.md para el diseño completo.
"""
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
    """Las 12 actividades informativas — no se reservan aquí, solo se muestran."""
    return PublicoService(db).listar_servicios_informativos()


@router.get("/unidades-hospedaje", response_model=list[UnidadHospedajePublicoOut])
def listar_unidades_hospedaje(db: Session = Depends(get_db)):
    """Habitación 1, Habitación 2, Cabaña 1 — para que el visitante elija."""
    return PublicoService(db).listar_unidades_hospedaje()


@router.get("/fechas-bloqueadas", response_model=list[FechaBloqueadaPublicaOut])
def listar_fechas_bloqueadas(
    desde: date = Query(...),
    hasta: date = Query(...),
    db: Session = Depends(get_db),
):
    """Publica únicamente rangos cerrados; títulos y notas siguen privados."""
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
    ):
        return {"disponible": False}
    disponible = PublicoService(db).hay_disponibilidad(unidad_hospedaje_id, fecha_llegada, fecha_salida)
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
    """
    Calcula el precio real SIN crear ninguna reservación — el paso 1
    del asistente (tipo + fechas) lo llama para mostrar el total antes
    de pedir los datos de contacto.
    """
    BloqueoOperativoService(db).validar_disponibilidad(
        fecha_llegada,
        fecha_salida,
        tipo_reservacion,
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
def crear_solicitud_reservacion(data: ReservacionPublicaCreate, request: Request, db: Session = Depends(get_db)):
    """
    Crea la reservación en estado "pendiente" (sin pago todavía — se
    agrega en una fase posterior) y notifica al administrador por
    correo (si está configurado) — siempre queda visible de inmediato
    en el sistema interno, sin importar si el correo se envía o no.

    AL-04: protegido con Idempotency-Key real — un doble clic/reintento
    de red con la misma clave nunca crea una segunda solicitud.
    """
    BloqueoOperativoService(db).validar_disponibilidad(
        data.fecha_llegada,
        data.fecha_salida,
        data.tipo_reservacion,
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

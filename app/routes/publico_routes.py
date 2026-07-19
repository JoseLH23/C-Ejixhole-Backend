"""Rutas públicas del portal de reservaciones."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.idempotency import ejecutar_con_idempotencia
from app.core.limites_publicos import limitar_desafio, limitar_envio, limitar_lectura
from app.database import get_db
from app.schemas.publico import (
    CotizacionOut,
    DisponibilidadOut,
    FechaBloqueadaPublicaOut,
    FormChallengeOut,
    PeriodoNoDisponibleOut,
    ReservacionPublicaCreate,
    ReservacionPublicaOut,
    ServicioPublicoOut,
    UnidadHospedajePublicoOut,
)
from app.services.audit_service import AuditService, obtener_id_entidad
from app.services.bloqueo_operativo_service import BloqueoOperativoService
from app.services.formulario_publico_service import FormularioPublicoService
from app.services.publico_service import PublicoService

router = APIRouter(prefix="/publico", tags=["Portal público"])


def _validar_rango(desde: date, hasta: date) -> None:
    if hasta < desde:
        raise HTTPException(status_code=400, detail="hasta no puede ser anterior a desde")
    if (hasta - desde).days > 366:
        raise HTTPException(status_code=400, detail="El rango máximo permitido es de 366 días")


@router.get("/servicios", response_model=list[ServicioPublicoOut], dependencies=[Depends(limitar_lectura)])
def listar_servicios_informativos(db: Session = Depends(get_db)):
    return PublicoService(db).listar_servicios_informativos()


@router.get("/unidades-hospedaje", response_model=list[UnidadHospedajePublicoOut], dependencies=[Depends(limitar_lectura)])
def listar_unidades_hospedaje(db: Session = Depends(get_db)):
    return PublicoService(db).listar_unidades_hospedaje()


@router.get("/fechas-bloqueadas", response_model=list[FechaBloqueadaPublicaOut], dependencies=[Depends(limitar_lectura)])
def listar_fechas_bloqueadas(desde: date = Query(...), hasta: date = Query(...), db: Session = Depends(get_db)):
    _validar_rango(desde, hasta)
    return BloqueoOperativoService(db).listar_bloqueos(desde, hasta)


@router.get("/disponibilidad-calendario", response_model=list[PeriodoNoDisponibleOut], dependencies=[Depends(limitar_lectura)])
def listar_disponibilidad_calendario(
    unidad_hospedaje_id: int = Query(..., gt=0),
    desde: date = Query(...),
    hasta: date = Query(...),
    db: Session = Depends(get_db),
):
    _validar_rango(desde, hasta)
    return PublicoService(db).listar_periodos_no_disponibles(unidad_hospedaje_id, desde, hasta)


@router.get("/disponibilidad", response_model=DisponibilidadOut, dependencies=[Depends(limitar_lectura)])
def verificar_disponibilidad(
    unidad_hospedaje_id: int = Query(...),
    fecha_llegada: date = Query(...),
    fecha_salida: date = Query(...),
    db: Session = Depends(get_db),
):
    if not BloqueoOperativoService(db).hay_disponibilidad(fecha_llegada, fecha_salida, "hospedaje", unidad_hospedaje_id):
        return {"disponible": False}
    return {"disponible": PublicoService(db).hay_disponibilidad(unidad_hospedaje_id, fecha_llegada, fecha_salida)}


@router.get("/cotizar", response_model=CotizacionOut, dependencies=[Depends(limitar_lectura)])
def cotizar_reservacion(
    tipo_reservacion: str = Query(...),
    fecha_llegada: date = Query(...),
    fecha_salida: date = Query(...),
    num_personas: int = Query(..., gt=0),
    unidad_hospedaje_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    BloqueoOperativoService(db).validar_disponibilidad(fecha_llegada, fecha_salida, tipo_reservacion, unidad_hospedaje_id)
    noches, total, desglose = PublicoService(db).cotizar(
        tipo_reservacion=tipo_reservacion,
        fecha_llegada=fecha_llegada,
        fecha_salida=fecha_salida,
        num_personas=num_personas,
        unidad_hospedaje_id=unidad_hospedaje_id,
    )
    return {"noches": noches, "total": total, "desglose": desglose}


@router.get("/form-challenge", response_model=FormChallengeOut, dependencies=[Depends(limitar_desafio)])
def obtener_desafio_formulario(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return FormularioPublicoService(db).create_challenge()


@router.post(
    "/reservaciones",
    response_model=ReservacionPublicaOut,
    status_code=201,
    dependencies=[Depends(limitar_envio)],
)
def crear_solicitud_reservacion(data: ReservacionPublicaCreate, request: Request, db: Session = Depends(get_db)):
    servicio = PublicoService(db)

    def crear_protegida():
        guardia = FormularioPublicoService(db)
        intento = guardia.validate_and_reserve(request, data)
        try:
            BloqueoOperativoService(db).validar_disponibilidad(
                data.fecha_llegada,
                data.fecha_salida,
                data.tipo_reservacion,
                data.unidad_hospedaje_id,
            )
            return servicio.crear_solicitud_reservacion(
                nombre_completo=data.nombre_completo,
                email=data.email,
                telefono=data.telefono,
                tipo_reservacion=data.tipo_reservacion,
                fecha_llegada=data.fecha_llegada,
                fecha_salida=data.fecha_salida,
                num_personas=data.num_personas,
                unidad_hospedaje_id=data.unidad_hospedaje_id,
                notas=data.notas,
            )
        except Exception:
            guardia.release(intento)
            raise

    resultado = ejecutar_con_idempotencia(
        db,
        request,
        endpoint="publico_crear_reservacion",
        cuerpo=data,
        operacion=crear_protegida,
        schema_salida=ReservacionPublicaOut,
    )
    AuditService(db).registrar(
        actor=None,
        accion="reservacion.solicitud_publica_creada",
        entidad_tipo="reservacion",
        entidad_id=obtener_id_entidad(resultado),
        request=request,
        despues=resultado,
        contexto={
            "tipo_reservacion": data.tipo_reservacion,
            "fecha_llegada": data.fecha_llegada,
            "fecha_salida": data.fecha_salida,
            "num_personas": data.num_personas,
            "unidad_hospedaje_id": data.unidad_hospedaje_id,
        },
        origen="portal_publico",
    )
    return resultado

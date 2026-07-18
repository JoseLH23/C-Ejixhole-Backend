"""Rutas de Caja. Protegidas con JWT + rol admin, operador o cajero."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.idempotency import ejecutar_con_idempotencia
from app.database import get_db
from app.dependencies import require_roles
from app.models.usuario import Usuario
from app.schemas.caja import CajaAbrirRequest, CajaCerrarRequest, CajaCorteDiaOut, CajaMovimientoCreate, CajaMovimientoOut, CajaSesionOut
from app.services.audit_service import AuditService, obtener_id_entidad, snapshot
from app.services.caja_service import CajaService

router = APIRouter(
    prefix="/caja",
    tags=["Caja"],
    dependencies=[Depends(require_roles("admin", "operador", "cajero"))],
)


@router.post("/abrir", response_model=CajaSesionOut, status_code=201)
def abrir_caja(
    data: CajaAbrirRequest,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(require_roles("admin", "operador", "cajero")),
):
    service = CajaService(db)
    resultado = ejecutar_con_idempotencia(
        db,
        request,
        endpoint="abrir_caja",
        cuerpo=data,
        operacion=lambda: service.abrir_sesion(usuario_id=usuario_actual.id, monto_apertura=data.monto_apertura),
        schema_salida=CajaSesionOut,
    )
    AuditService(db).registrar(
        actor=usuario_actual,
        accion="caja.abierta",
        entidad_tipo="caja_sesion",
        entidad_id=obtener_id_entidad(resultado),
        request=request,
        despues=resultado,
        contexto={"monto_apertura": data.monto_apertura},
    )
    return resultado


@router.get("", response_model=list[CajaSesionOut])
def listar_sesiones(
    usuario_id: Optional[int] = None,
    estado: Optional[str] = None,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return CajaService(db).listar_sesiones(usuario_id=usuario_id, estado=estado, limit=limit, offset=offset)


@router.get("/corte-dia", response_model=CajaCorteDiaOut)
def corte_dia(
    fecha: Optional[date] = None,
    usuario_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    return CajaService(db).obtener_corte_dia(fecha=fecha, usuario_id=usuario_id)


@router.get("/{sesion_id}", response_model=CajaSesionOut)
def obtener_sesion(sesion_id: int, db: Session = Depends(get_db)):
    return CajaService(db).obtener_sesion_por_id(sesion_id)


@router.post("/{sesion_id}/movimientos", response_model=CajaMovimientoOut, status_code=201)
def registrar_movimiento(
    sesion_id: int,
    data: CajaMovimientoCreate,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(require_roles("admin", "operador", "cajero")),
):
    service = CajaService(db)
    resultado = ejecutar_con_idempotencia(
        db,
        request,
        endpoint="registrar_movimiento_caja",
        cuerpo=data,
        operacion=lambda: service.registrar_movimiento(
            sesion_id=sesion_id,
            usuario_id=usuario_actual.id,
            tipo=data.tipo,
            monto=data.monto,
            concepto=data.concepto,
        ),
        schema_salida=CajaMovimientoOut,
    )
    AuditService(db).registrar(
        actor=usuario_actual,
        accion="caja.movimiento_registrado",
        entidad_tipo="caja_movimiento",
        entidad_id=obtener_id_entidad(resultado),
        request=request,
        despues=resultado,
        contexto={"sesion_id": sesion_id, "tipo": data.tipo, "monto": data.monto},
    )
    return resultado


@router.get("/{sesion_id}/movimientos", response_model=list[CajaMovimientoOut])
def listar_movimientos(sesion_id: int, db: Session = Depends(get_db)):
    return CajaService(db).listar_movimientos(sesion_id)


@router.post("/{sesion_id}/cerrar", response_model=CajaSesionOut)
def cerrar_caja(
    sesion_id: int,
    data: CajaCerrarRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_roles("admin", "operador", "cajero")),
):
    service = CajaService(db)
    antes = snapshot(service.obtener_sesion_por_id(sesion_id))
    resultado = service.cerrar_sesion(sesion_id, data.monto_cierre_real)
    AuditService(db).registrar(
        actor=actor,
        accion="caja.cerrada",
        entidad_tipo="caja_sesion",
        entidad_id=sesion_id,
        request=request,
        antes=antes,
        despues=resultado,
        contexto={"monto_cierre_real": data.monto_cierre_real},
    )
    return resultado

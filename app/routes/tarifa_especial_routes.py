from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models.usuario import Usuario
from app.schemas.tarifa_especial import (
    SimulacionTarifaInput,
    SimulacionTarifaOut,
    TarifaEspecialCreate,
    TarifaEspecialOut,
    TarifaEspecialUpdate,
)
from app.services.audit_service import AuditService, snapshot
from app.services.tarifa_especial_service import TarifaEspecialService

router = APIRouter(
    prefix="/tarifas-especiales",
    tags=["Tarifas especiales"],
    dependencies=[Depends(require_roles("admin"))],
)


@router.get("", response_model=list[TarifaEspecialOut])
def listar_tarifas(db: Session = Depends(get_db)):
    return TarifaEspecialService(db).listar()


@router.post("/simular", response_model=SimulacionTarifaOut)
def simular_tarifa(data: SimulacionTarifaInput, db: Session = Depends(get_db)):
    payload = data.model_dump()
    candidata = payload.pop("candidata")
    candidata["activa"] = True
    return TarifaEspecialService(db).simular(**payload, candidata=candidata)


@router.post("", response_model=TarifaEspecialOut, status_code=201)
def crear_tarifa(
    data: TarifaEspecialCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_roles("admin")),
):
    tarifa = TarifaEspecialService(db).crear(**data.model_dump())
    AuditService(db).registrar(
        actor=actor,
        accion="tarifa.creada",
        entidad_tipo="tarifa_especial",
        entidad_id=tarifa.id,
        request=request,
        despues=tarifa,
    )
    return tarifa


@router.put("/{tarifa_id}", response_model=TarifaEspecialOut)
def actualizar_tarifa(
    tarifa_id: int,
    data: TarifaEspecialUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_roles("admin")),
):
    service = TarifaEspecialService(db)
    antes = snapshot(service.obtener(tarifa_id))
    tarifa = service.actualizar(tarifa_id, **data.model_dump(exclude_unset=True))
    AuditService(db).registrar(
        actor=actor,
        accion="tarifa.actualizada",
        entidad_tipo="tarifa_especial",
        entidad_id=tarifa.id,
        request=request,
        antes=antes,
        despues=tarifa,
    )
    return tarifa


@router.delete("/{tarifa_id}", status_code=204)
def eliminar_tarifa(
    tarifa_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_roles("admin")),
):
    service = TarifaEspecialService(db)
    antes = snapshot(service.obtener(tarifa_id))
    service.eliminar(tarifa_id)
    AuditService(db).registrar(
        actor=actor,
        accion="tarifa.eliminada",
        entidad_tipo="tarifa_especial",
        entidad_id=tarifa_id,
        request=request,
        antes=antes,
    )
    return Response(status_code=204)

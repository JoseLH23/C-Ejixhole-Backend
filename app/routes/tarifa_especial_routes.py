from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.tarifa_especial import (
    SimulacionTarifaInput,
    SimulacionTarifaOut,
    TarifaEspecialCreate,
    TarifaEspecialOut,
    TarifaEspecialUpdate,
)
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
def crear_tarifa(data: TarifaEspecialCreate, db: Session = Depends(get_db)):
    return TarifaEspecialService(db).crear(**data.model_dump())


@router.put("/{tarifa_id}", response_model=TarifaEspecialOut)
def actualizar_tarifa(tarifa_id: int, data: TarifaEspecialUpdate, db: Session = Depends(get_db)):
    return TarifaEspecialService(db).actualizar(tarifa_id, **data.model_dump(exclude_unset=True))


@router.delete("/{tarifa_id}", status_code=204)
def eliminar_tarifa(tarifa_id: int, db: Session = Depends(get_db)):
    TarifaEspecialService(db).eliminar(tarifa_id)
    return Response(status_code=204)

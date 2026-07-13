"""
Rutas de Servicios. Protegidas con JWT + rol: admin únicamente
(ver docs/modulos/permisos-por-rol.md).
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.servicio import ServicioCreate, ServicioOut, ServicioUpdate
from app.services.servicio_service import ServicioService

router = APIRouter(prefix="/servicios", tags=["Servicios"], dependencies=[Depends(require_roles("admin"))])


@router.post("", response_model=ServicioOut, status_code=201)
def crear_servicio(data: ServicioCreate, db: Session = Depends(get_db)):
    service = ServicioService(db)
    return service.crear(
        nombre=data.nombre,
        descripcion=data.descripcion,
        precio=data.precio,
        duracion_minutos=data.duracion_minutos,
        capacidad_maxima=data.capacidad_maxima,
        categoria=data.categoria,
    )


@router.get("", response_model=list[ServicioOut])
def listar_servicios(
    solo_activos: bool = True,
    categoria: Optional[str] = None,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    service = ServicioService(db)
    return service.listar(solo_activos=solo_activos, categoria=categoria, limit=limit, offset=offset)


@router.get("/{servicio_id}", response_model=ServicioOut)
def obtener_servicio(servicio_id: int, db: Session = Depends(get_db)):
    service = ServicioService(db)
    return service.obtener_por_id(servicio_id)


@router.put("/{servicio_id}", response_model=ServicioOut)
def actualizar_servicio(servicio_id: int, data: ServicioUpdate, db: Session = Depends(get_db)):
    service = ServicioService(db)
    return service.actualizar(servicio_id, data.model_dump(exclude_unset=True))


@router.delete("/{servicio_id}", response_model=ServicioOut)
def desactivar_servicio(servicio_id: int, db: Session = Depends(get_db)):
    """Soft delete: marca activo=False, no borra el registro."""
    service = ServicioService(db)
    return service.desactivar(servicio_id)

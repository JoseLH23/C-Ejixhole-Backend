"""
Rutas de Clientes. Protegidas con JWT + rol: admin y operador
únicamente (ver docs/modulos/permisos-por-rol.md).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.cliente import ClienteCreate, ClienteDuplicadoWarning, ClienteOut, ClienteUpdate
from app.services.cliente_service import ClienteService

router = APIRouter(
    prefix="/clientes", tags=["Clientes"], dependencies=[Depends(require_roles("admin", "operador"))]
)


@router.post("", response_model=ClienteDuplicadoWarning, status_code=201)
def crear_cliente(data: ClienteCreate, db: Session = Depends(get_db)):
    service = ClienteService(db)
    cliente, duplicados = service.crear(
        data.nombre, data.apellido, data.telefono, data.email, data.notas
    )
    return ClienteDuplicadoWarning(posibles_duplicados=duplicados, cliente_creado=cliente)


@router.get("", response_model=list[ClienteOut])
def listar_clientes(
    solo_activos: bool = True,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    service = ClienteService(db)
    return service.listar(solo_activos=solo_activos, limit=limit, offset=offset)


@router.get("/{cliente_id}", response_model=ClienteOut)
def obtener_cliente(cliente_id: int, db: Session = Depends(get_db)):
    service = ClienteService(db)
    return service.obtener_por_id(cliente_id)


@router.put("/{cliente_id}", response_model=ClienteOut)
def actualizar_cliente(cliente_id: int, data: ClienteUpdate, db: Session = Depends(get_db)):
    service = ClienteService(db)
    return service.actualizar(cliente_id, data.model_dump(exclude_unset=True))


@router.delete("/{cliente_id}", response_model=ClienteOut)
def desactivar_cliente(cliente_id: int, db: Session = Depends(get_db)):
    """Soft delete: marca activo=False, no borra el registro."""
    service = ClienteService(db)
    return service.desactivar(cliente_id)

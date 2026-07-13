from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ClienteCreate(BaseModel):
    nombre: str
    apellido: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    notas: Optional[str] = None


class ClienteUpdate(BaseModel):
    """Todos los campos opcionales: solo se actualiza lo que se envía."""
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    notas: Optional[str] = None


class ClienteOut(BaseModel):
    id: int
    nombre: str
    apellido: Optional[str]
    telefono: Optional[str]
    email: Optional[str]
    notas: Optional[str]
    activo: bool
    fecha_creacion: datetime
    fecha_actualizacion: datetime

    model_config = ConfigDict(from_attributes=True)


class ClienteDuplicadoWarning(BaseModel):
    """Se devuelve junto al cliente creado si se detectó una posible coincidencia
    de teléfono o email con un cliente ya existente."""
    posibles_duplicados: list[ClienteOut]
    cliente_creado: ClienteOut

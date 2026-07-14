from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# AL-10 (auditoría de seguridad 13/jul/2026): mismo criterio que se
# aplicó a los schemas públicos — límites reales, no solo "opcional".
class ClienteCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=150)
    apellido: Optional[str] = Field(default=None, max_length=150)
    telefono: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)
    notas: Optional[str] = Field(default=None, max_length=1000)


class ClienteUpdate(BaseModel):
    """Todos los campos opcionales: solo se actualiza lo que se envía."""
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=150)
    apellido: Optional[str] = Field(default=None, max_length=150)
    telefono: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)
    notas: Optional[str] = Field(default=None, max_length=1000)


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

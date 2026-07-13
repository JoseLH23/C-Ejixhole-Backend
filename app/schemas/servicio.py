from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator, ConfigDict


class ServicioCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    precio: Decimal
    duracion_minutos: Optional[int] = None
    capacidad_maxima: Optional[int] = None
    categoria: Optional[str] = None

    @field_validator("precio")
    @classmethod
    def precio_no_negativo(cls, v):
        if v < 0:
            raise ValueError("precio no puede ser negativo")
        return v

    @field_validator("duracion_minutos")
    @classmethod
    def duracion_positiva(cls, v):
        if v is not None and v <= 0:
            raise ValueError("duracion_minutos debe ser mayor a 0")
        return v

    @field_validator("capacidad_maxima")
    @classmethod
    def capacidad_positiva(cls, v):
        if v is not None and v <= 0:
            raise ValueError("capacidad_maxima debe ser mayor a 0")
        return v


class ServicioUpdate(BaseModel):
    """Todos los campos opcionales: solo se actualiza lo que se envía."""
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    precio: Optional[Decimal] = None
    duracion_minutos: Optional[int] = None
    capacidad_maxima: Optional[int] = None
    categoria: Optional[str] = None

    @field_validator("precio")
    @classmethod
    def precio_no_negativo(cls, v):
        if v is not None and v < 0:
            raise ValueError("precio no puede ser negativo")
        return v


class ServicioOut(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str]
    precio: Decimal
    duracion_minutos: Optional[int]
    capacidad_maxima: Optional[int]
    categoria: Optional[str]
    activo: bool
    fecha_creacion: datetime
    fecha_actualizacion: datetime

    model_config = ConfigDict(from_attributes=True)

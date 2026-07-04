from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator

from app.models.reservacion import ESTADOS_RESERVACION, ORIGENES_RESERVACION


class ReservacionCreate(BaseModel):
    cliente_id: int
    servicio_id: int
    # Temporal: hasta que exista el módulo Auth/Usuarios, quien crea la
    # reservación se indica explícitamente. Cuando exista JWT, este
    # campo se elimina y se toma del usuario autenticado.
    usuario_id: int
    fecha_visita: date
    num_personas: int
    origen: str = "recepcion"
    notas: Optional[str] = None

    @field_validator("num_personas")
    @classmethod
    def num_personas_positivo(cls, v):
        if v <= 0:
            raise ValueError("num_personas debe ser mayor a 0")
        return v

    @field_validator("origen")
    @classmethod
    def origen_valido(cls, v):
        if v not in ORIGENES_RESERVACION:
            raise ValueError(f"origen debe ser uno de: {ORIGENES_RESERVACION}")
        return v


class ReservacionEstadoUpdate(BaseModel):
    nuevo_estado: str

    @field_validator("nuevo_estado")
    @classmethod
    def estado_valido(cls, v):
        if v not in ESTADOS_RESERVACION:
            raise ValueError(f"estado debe ser uno de: {ESTADOS_RESERVACION}")
        return v


class ReservacionOut(BaseModel):
    id: int
    cliente_id: int
    servicio_id: int
    usuario_id: int
    fecha_reservacion: datetime
    fecha_visita: date
    num_personas: int
    estado: str
    origen: str
    total: Decimal
    monto_pagado: Decimal
    saldo_pendiente: Decimal
    notas: Optional[str]
    fecha_creacion: datetime
    fecha_actualizacion: datetime

    class Config:
        from_attributes = True

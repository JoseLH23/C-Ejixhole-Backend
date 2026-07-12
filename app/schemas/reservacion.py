from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator

from app.models.reservacion import ESTADOS_RESERVACION, ORIGENES_RESERVACION, TIPOS_RESERVACION


class ReservacionCreate(BaseModel):
    cliente_id: int
    servicio_id: int
    # Temporal: hasta que exista el módulo Auth/Usuarios, quien crea la
    # reservación se indica explícitamente. Cuando exista JWT, este
    # campo se elimina y se toma del usuario autenticado.
    usuario_id: int
    num_personas: int
    origen: str = "recepcion"
    notas: Optional[str] = None

    # Nuevo (Fase portal público): tipo de reservación y sus fechas.
    # Para "entrada" (visita de un día), llegada y salida deben ser el
    # mismo día. Para "camping"/"hospedaje", salida debe ser posterior
    # a llegada (al menos 1 noche).
    tipo_reservacion: str = "entrada"
    fecha_llegada: date
    fecha_salida: date
    # Solo obligatorio (y solo válido) cuando tipo_reservacion == "hospedaje".
    unidad_hospedaje_id: Optional[int] = None

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

    @field_validator("tipo_reservacion")
    @classmethod
    def tipo_valido(cls, v):
        if v not in TIPOS_RESERVACION:
            raise ValueError(f"tipo_reservacion debe ser uno de: {TIPOS_RESERVACION}")
        return v

    @model_validator(mode="after")
    def fechas_y_unidad_consistentes(self):
        if self.fecha_salida < self.fecha_llegada:
            raise ValueError("fecha_salida no puede ser anterior a fecha_llegada")

        if self.tipo_reservacion == "entrada" and self.fecha_salida != self.fecha_llegada:
            raise ValueError("Para 'entrada' (visita de un día), fecha_llegada y fecha_salida deben ser el mismo día")

        if self.tipo_reservacion in ("camping", "hospedaje") and self.fecha_salida == self.fecha_llegada:
            raise ValueError(f"Para '{self.tipo_reservacion}' se necesita al menos 1 noche (fecha_salida posterior a fecha_llegada)")

        if self.tipo_reservacion == "hospedaje" and self.unidad_hospedaje_id is None:
            raise ValueError("unidad_hospedaje_id es obligatorio cuando tipo_reservacion es 'hospedaje'")

        if self.tipo_reservacion != "hospedaje" and self.unidad_hospedaje_id is not None:
            raise ValueError("unidad_hospedaje_id solo aplica cuando tipo_reservacion es 'hospedaje'")

        return self


class ReservacionEstadoUpdate(BaseModel):
    nuevo_estado: str

    @field_validator("nuevo_estado")
    @classmethod
    def estado_valido(cls, v):
        if v not in ESTADOS_RESERVACION:
            raise ValueError(f"estado debe ser uno de: {ESTADOS_RESERVACION}")
        return v


class ReservacionUpdate(BaseModel):
    """
    Todos los campos opcionales: solo se actualiza lo que se envía
    (mismo criterio que ClienteUpdate/ServicioUpdate). No incluye
    `tipo_reservacion` a propósito — ver docstring de
    ReservacionService.actualizar().
    """
    servicio_id: Optional[int] = None
    fecha_llegada: Optional[date] = None
    fecha_salida: Optional[date] = None
    num_personas: Optional[int] = None
    unidad_hospedaje_id: Optional[int] = None
    notas: Optional[str] = None

    @field_validator("num_personas")
    @classmethod
    def num_personas_positivo(cls, v):
        if v is not None and v <= 0:
            raise ValueError("num_personas debe ser mayor a 0")
        return v


class ReservacionOut(BaseModel):
    id: int
    cliente_id: int
    servicio_id: int
    usuario_id: Optional[int]
    unidad_hospedaje_id: Optional[int]
    fecha_reservacion: datetime
    fecha_visita: date
    fecha_llegada: Optional[date]
    fecha_salida: Optional[date]
    num_personas: int
    estado: str
    origen: str
    tipo_reservacion: str
    total: Decimal
    monto_pagado: Decimal
    saldo_pendiente: Decimal
    notas: Optional[str]
    fecha_creacion: datetime
    fecha_actualizacion: datetime

    class Config:
        from_attributes = True

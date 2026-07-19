from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator, ConfigDict

from app.models.reservacion import TIPOS_RESERVACION


class ServicioPublicoOut(BaseModel):
    nombre: str
    descripcion: Optional[str]
    precio: Decimal
    model_config = ConfigDict(from_attributes=True)


class UnidadHospedajePublicoOut(BaseModel):
    id: int
    nombre: str
    capacidad_maxima: int
    precio_por_noche: Decimal
    model_config = ConfigDict(from_attributes=True)


class DisponibilidadOut(BaseModel):
    disponible: bool


class FechaBloqueadaPublicaOut(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    model_config = ConfigDict(from_attributes=True)


class PeriodoNoDisponibleOut(BaseModel):
    """Rango público sin datos personales ni detalles operativos internos."""
    fecha_inicio: date
    fecha_fin: date
    motivo: Literal["ocupado", "bloqueado"]


class ConceptoPrecio(BaseModel):
    concepto: str
    detalle: str
    subtotal: Decimal


class CotizacionOut(BaseModel):
    noches: int
    total: Decimal
    desglose: list[ConceptoPrecio]


class FormChallengeOut(BaseModel):
    token: str
    issued_at: datetime
    expires_at: datetime
    minimum_wait_seconds: int
    enforcement_mode: Literal["monitor", "enforce"]


class ReservacionPublicaCreate(BaseModel):
    nombre_completo: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    telefono: str = Field(..., min_length=7, max_length=20)
    tipo_reservacion: str
    fecha_llegada: date
    fecha_salida: date
    num_personas: int = Field(..., gt=0, le=50)
    unidad_hospedaje_id: Optional[int] = None
    notas: Optional[str] = Field(default=None, max_length=1000)
    website: str = Field(default="", max_length=200, exclude=True)
    form_challenge: Optional[str] = Field(default=None, max_length=1000, exclude=True)

    @field_validator("nombre_completo")
    @classmethod
    def nombre_no_vacio(cls, v):
        if not v.strip():
            raise ValueError("nombre_completo no puede estar vacío")
        return v.strip()

    @field_validator("telefono")
    @classmethod
    def telefono_no_vacio(cls, v):
        if not v.strip():
            raise ValueError("telefono no puede estar vacío")
        return v.strip()

    @field_validator("num_personas")
    @classmethod
    def num_personas_positivo(cls, v):
        if v <= 0:
            raise ValueError("num_personas debe ser mayor a 0")
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
            raise ValueError("Para una visita de un día, fecha_llegada y fecha_salida deben ser el mismo día")
        if self.tipo_reservacion in ("camping", "hospedaje") and self.fecha_salida == self.fecha_llegada:
            raise ValueError(f"Para '{self.tipo_reservacion}' se necesita al menos 1 noche")
        if self.tipo_reservacion == "hospedaje" and self.unidad_hospedaje_id is None:
            raise ValueError("Debes elegir una habitación/cabaña para este tipo de reservación")
        if self.tipo_reservacion != "hospedaje" and self.unidad_hospedaje_id is not None:
            raise ValueError("unidad_hospedaje_id solo aplica para hospedaje")
        return self


class ReservacionPublicaOut(BaseModel):
    id: int
    tipo_reservacion: str
    fecha_llegada: date
    fecha_salida: date
    num_personas: int
    total: Decimal
    estado: str
    fecha_creacion: datetime
    mensaje: str = "Tu solicitud fue recibida. Te confirmaremos pronto por correo o teléfono."
    model_config = ConfigDict(from_attributes=True)

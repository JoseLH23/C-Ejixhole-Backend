from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator, ConfigDict

from app.models.pago import METODOS_PAGO, TIPOS_PAGO


class PagoCreate(BaseModel):
    reservacion_id: int
    monto: Decimal
    tipo: str
    metodo_pago: str
    referencia: Optional[str] = None
    notas: Optional[str] = None

    @field_validator("monto")
    @classmethod
    def monto_positivo(cls, v):
        if v <= 0:
            raise ValueError("monto debe ser mayor a 0")
        return v

    @field_validator("tipo")
    @classmethod
    def tipo_valido(cls, v):
        if v not in TIPOS_PAGO:
            raise ValueError(f"tipo debe ser uno de: {TIPOS_PAGO}")
        return v

    @field_validator("metodo_pago")
    @classmethod
    def metodo_valido(cls, v):
        if v not in METODOS_PAGO:
            raise ValueError(f"metodo_pago debe ser uno de: {METODOS_PAGO}")
        return v


class PagoOut(BaseModel):
    id: int
    reservacion_id: int
    usuario_id: int
    monto: Decimal
    tipo: str
    metodo_pago: str
    referencia: Optional[str]
    notas: Optional[str]
    fecha_pago: datetime

    model_config = ConfigDict(from_attributes=True)

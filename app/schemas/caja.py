from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator, ConfigDict

from app.models.caja import TIPOS_MOVIMIENTO


class CajaAbrirRequest(BaseModel):
    usuario_id: int
    # Temporal: igual que en Reservaciones/Pagos, hasta que exista un
    # flujo que tome el usuario del token en vez de pedirlo explícito.
    monto_apertura: Decimal = Decimal("0")

    @field_validator("monto_apertura")
    @classmethod
    def monto_no_negativo(cls, v):
        if v < 0:
            raise ValueError("monto_apertura no puede ser negativo")
        return v


class CajaCerrarRequest(BaseModel):
    monto_cierre_real: Decimal

    @field_validator("monto_cierre_real")
    @classmethod
    def monto_no_negativo(cls, v):
        if v < 0:
            raise ValueError("monto_cierre_real no puede ser negativo")
        return v


class CajaMovimientoCreate(BaseModel):
    usuario_id: int
    tipo: str
    monto: Decimal
    concepto: str

    @field_validator("tipo")
    @classmethod
    def tipo_valido(cls, v):
        if v not in TIPOS_MOVIMIENTO:
            raise ValueError(f"tipo debe ser uno de: {TIPOS_MOVIMIENTO}")
        return v

    @field_validator("monto")
    @classmethod
    def monto_positivo(cls, v):
        if v <= 0:
            raise ValueError("monto debe ser mayor a 0")
        return v


class CajaMovimientoOut(BaseModel):
    id: int
    caja_sesion_id: int
    tipo: str
    monto: Decimal
    concepto: str
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)


class CajaSesionOut(BaseModel):
    id: int
    usuario_id: int
    fecha_apertura: datetime
    monto_apertura: Decimal
    fecha_cierre: Optional[datetime]
    monto_cierre_esperado: Optional[Decimal]
    monto_cierre_real: Optional[Decimal]
    diferencia: Optional[Decimal]
    estado: str
    saldo_actual: Decimal
    notas: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class CajaCorteDiaOut(BaseModel):
    fecha: date
    num_sesiones: int
    total_ingresos: Decimal
    total_egresos: Decimal
    saldo_neto: Decimal
    sesiones: list[CajaSesionOut]

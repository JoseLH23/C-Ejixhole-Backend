from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AplicaTarifa = Literal["todos", "entrada", "camping", "hospedaje"]


class TarifaEspecialCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    descripcion: str | None = Field(default=None, max_length=2000)
    fecha_inicio: date
    fecha_fin: date
    porcentaje_ajuste: Decimal = Field(ge=-100, le=500)
    aplica_a: AplicaTarifa = "todos"
    dias_semana: list[int] | None = None
    prioridad: int = Field(default=0, ge=-1000, le=1000)
    unidad_hospedaje_id: int | None = None
    activa: bool = True

    @model_validator(mode="after")
    def validar(self):
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin no puede ser anterior a fecha_inicio")
        if self.dias_semana is not None:
            dias = sorted(set(self.dias_semana))
            if any(dia < 0 or dia > 6 for dia in dias):
                raise ValueError("dias_semana debe usar valores entre 0 (lunes) y 6 (domingo)")
            self.dias_semana = dias
        if self.unidad_hospedaje_id is not None and self.aplica_a not in ("todos", "hospedaje"):
            raise ValueError("unidad_hospedaje_id solo aplica a hospedaje")
        return self


class TarifaEspecialUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    descripcion: str | None = Field(default=None, max_length=2000)
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    porcentaje_ajuste: Decimal | None = Field(default=None, ge=-100, le=500)
    aplica_a: AplicaTarifa | None = None
    dias_semana: list[int] | None = None
    prioridad: int | None = Field(default=None, ge=-1000, le=1000)
    unidad_hospedaje_id: int | None = None
    activa: bool | None = None


class TarifaEspecialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    descripcion: str | None
    fecha_inicio: date
    fecha_fin: date
    porcentaje_ajuste: Decimal
    aplica_a: AplicaTarifa
    dias_semana: list[int] | None
    prioridad: int
    unidad_hospedaje_id: int | None
    activa: bool
    fecha_creacion: datetime
    fecha_actualizacion: datetime

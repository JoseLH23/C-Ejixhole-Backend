from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TipoEventoCalendario = Literal["bloqueo", "mantenimiento", "recordatorio", "campana"]


class EventoCalendarioCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=120)
    tipo: TipoEventoCalendario
    fecha_inicio: date
    fecha_fin: date
    notas: str | None = Field(default=None, max_length=2000)
    unidad_hospedaje_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def unidad_solo_en_bloqueos(self):
        if self.unidad_hospedaje_id is not None and self.tipo != "bloqueo":
            raise ValueError("unidad_hospedaje_id solo puede usarse en eventos tipo bloqueo")
        return self


class EventoCalendarioOut(EventoCalendarioCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha_creacion: datetime
    fecha_actualizacion: datetime

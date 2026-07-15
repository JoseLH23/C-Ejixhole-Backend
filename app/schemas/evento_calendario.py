from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TipoEventoCalendario = Literal["bloqueo", "mantenimiento", "recordatorio", "campana"]


class EventoCalendarioCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=120)
    tipo: TipoEventoCalendario
    fecha_inicio: date
    fecha_fin: date
    notas: str | None = Field(default=None, max_length=2000)


class EventoCalendarioOut(EventoCalendarioCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha_creacion: datetime
    fecha_actualizacion: datetime

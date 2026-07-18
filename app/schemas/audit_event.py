from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_usuario_id: int | None
    actor_nombre: str | None
    actor_rol: str | None
    accion: str
    entidad_tipo: str
    entidad_id: str | None
    origen: str
    request_id: str | None
    antes: dict | None
    despues: dict | None
    contexto: dict | None
    fecha_creacion: datetime

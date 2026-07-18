from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from fastapi import HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.models.usuario import Usuario

_SECRET_KEYS = {
    "password",
    "password_hash",
    "nueva_password",
    "access_token",
    "token",
    "csrf",
    "csrf_token",
    "secret",
    "api_key",
    "idempotency_key",
    "clave",
}
_PII_KEYS = {
    "email",
    "telefono",
    "nombre_completo",
    "notas",
    "referencia",
}


def _normalizar_valor(valor):
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, BaseModel):
        return _sanitizar(valor.model_dump(mode="json"))
    if isinstance(valor, dict):
        return _sanitizar(valor)
    if isinstance(valor, (list, tuple, set)):
        return [_normalizar_valor(item) for item in valor]
    if isinstance(valor, (str, int, float, bool)) or valor is None:
        return valor
    return str(valor)


def _sanitizar(datos: dict) -> dict:
    resultado = {}
    for clave, valor in datos.items():
        clave_texto = str(clave)
        clave_normalizada = clave_texto.lower()
        if any(fragmento in clave_normalizada for fragmento in _SECRET_KEYS):
            resultado[clave_texto] = "[REDACTADO]"
        elif clave_normalizada in _PII_KEYS:
            resultado[clave_texto] = "[PROTEGIDO]" if valor not in (None, "") else valor
        else:
            resultado[clave_texto] = _normalizar_valor(valor)
    return resultado


def snapshot(objeto, campos: tuple[str, ...] | None = None) -> dict | None:
    if objeto is None:
        return None
    if isinstance(objeto, BaseModel):
        datos = objeto.model_dump(mode="json")
    elif isinstance(objeto, dict):
        datos = dict(objeto)
    else:
        mapper = inspect(objeto.__class__, raiseerr=False)
        if mapper is None:
            return {"valor": _normalizar_valor(objeto)}
        nombres = campos or tuple(columna.key for columna in mapper.columns)
        datos = {nombre: getattr(objeto, nombre, None) for nombre in nombres}
    if campos is not None:
        datos = {campo: datos.get(campo) for campo in campos if campo in datos}
    return _sanitizar(datos)


def obtener_id_entidad(resultado) -> str | None:
    if resultado is None:
        return None
    if isinstance(resultado, dict):
        valor = resultado.get("id")
    else:
        valor = getattr(resultado, "id", None)
    return str(valor) if valor is not None else None


def clave_de_request(request: Request | None, accion: str, entidad_id: str | None) -> str | None:
    if request is None:
        return None
    idempotencia = request.headers.get("idempotency-key")
    if idempotencia:
        return f"{accion}:idempotency:{idempotencia}"[:220]
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return f"{accion}:request:{request_id}:{entidad_id or '-'}"[:220]
    return None


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def registrar(
        self,
        *,
        actor: Usuario | None,
        accion: str,
        entidad_tipo: str,
        entidad_id: str | int | None,
        request: Request | None = None,
        antes=None,
        despues=None,
        contexto: dict | None = None,
        origen: str = "admin",
        event_key: str | None = None,
    ) -> AuditEvent:
        entidad_id_texto = str(entidad_id) if entidad_id is not None else None
        event_key = event_key or clave_de_request(request, accion, entidad_id_texto) or str(uuid4())
        existente = self.db.query(AuditEvent).filter(AuditEvent.event_key == event_key).first()
        if existente:
            return existente

        evento = AuditEvent(
            event_key=event_key,
            actor_usuario_id=getattr(actor, "id", None),
            actor_nombre=getattr(actor, "nombre", None),
            actor_rol=getattr(getattr(actor, "rol", None), "nombre", None),
            accion=accion,
            entidad_tipo=entidad_tipo,
            entidad_id=entidad_id_texto,
            origen=origen,
            request_id=(getattr(request.state, "request_id", None) if request else None),
            antes=snapshot(antes),
            despues=snapshot(despues),
            contexto=snapshot(contexto),
        )
        self.db.add(evento)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existente = self.db.query(AuditEvent).filter(AuditEvent.event_key == event_key).first()
            if existente:
                return existente
            raise
        self.db.refresh(evento)
        return evento

    def listar(
        self,
        *,
        entidad_tipo: str | None = None,
        entidad_id: str | None = None,
        accion: str | None = None,
        actor_usuario_id: int | None = None,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        query = self.db.query(AuditEvent)
        if entidad_tipo:
            query = query.filter(AuditEvent.entidad_tipo == entidad_tipo)
        if entidad_id:
            query = query.filter(AuditEvent.entidad_id == entidad_id)
        if accion:
            query = query.filter(AuditEvent.accion == accion)
        if actor_usuario_id is not None:
            query = query.filter(AuditEvent.actor_usuario_id == actor_usuario_id)
        if desde:
            query = query.filter(AuditEvent.fecha_creacion >= desde)
        if hasta:
            query = query.filter(AuditEvent.fecha_creacion <= hasta)
        return query.order_by(AuditEvent.fecha_creacion.desc(), AuditEvent.id.desc()).offset(offset).limit(limit).all()

    def obtener(self, evento_id: int) -> AuditEvent:
        evento = self.db.query(AuditEvent).filter(AuditEvent.id == evento_id).first()
        if not evento:
            raise HTTPException(status_code=404, detail="Evento de auditoría no encontrado")
        return evento

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.database import Base
from app.models.audit_event import AuditEvent
from app.models.usuario import Rol, Usuario
from app.services.audit_service import AuditService


def crear_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def crear_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/pagos",
            "headers": [
                (b"idempotency-key", b"operacion-auditada-1"),
                (b"x-request-id", b"request-auditado-1"),
            ],
            "state": {"request_id": "request-auditado-1"},
        }
    )


def test_registro_sanitiza_datos_y_conserva_actor():
    db = crear_db()
    rol = Rol(nombre="admin")
    actor = Usuario(
        nombre="Administrador",
        email="admin@example.com",
        password_hash="hash-secreto",
        rol=rol,
        activo=True,
    )
    db.add(actor)
    db.commit()
    db.refresh(actor)

    evento = AuditService(db).registrar(
        actor=actor,
        accion="pago.registrado",
        entidad_tipo="pago",
        entidad_id=12,
        request=crear_request(),
        despues={
            "id": 12,
            "monto": "500.00",
            "email": "cliente@example.com",
            "referencia": "ABC-123",
            "password_hash": "nunca-guardar",
        },
    )

    assert evento.actor_usuario_id == actor.id
    assert evento.actor_nombre == "Administrador"
    assert evento.actor_rol == "admin"
    assert evento.request_id == "request-auditado-1"
    assert evento.despues["monto"] == "500.00"
    assert evento.despues["email"] == "[PROTEGIDO]"
    assert evento.despues["referencia"] == "[PROTEGIDO]"
    assert evento.despues["password_hash"] == "[REDACTADO]"


def test_idempotencia_no_duplica_evento_de_auditoria():
    db = crear_db()
    service = AuditService(db)
    request = crear_request()

    primero = service.registrar(
        actor=None,
        accion="pago.registrado",
        entidad_tipo="pago",
        entidad_id=9,
        request=request,
        despues={"id": 9},
    )
    segundo = service.registrar(
        actor=None,
        accion="pago.registrado",
        entidad_tipo="pago",
        entidad_id=9,
        request=request,
        despues={"id": 9},
    )

    assert primero.id == segundo.id
    assert db.query(AuditEvent).count() == 1


def test_consulta_filtra_entidad_accion_y_actor():
    db = crear_db()
    service = AuditService(db)
    service.registrar(actor=None, accion="tarifa.creada", entidad_tipo="tarifa_especial", entidad_id=1)
    service.registrar(actor=None, accion="tarifa.actualizada", entidad_tipo="tarifa_especial", entidad_id=1)
    service.registrar(actor=None, accion="caja.abierta", entidad_tipo="caja_sesion", entidad_id=2)

    eventos = service.listar(entidad_tipo="tarifa_especial", entidad_id="1")
    assert len(eventos) == 2
    assert {evento.accion for evento in eventos} == {"tarifa.creada", "tarifa.actualizada"}


def test_api_de_auditoria_es_solo_lectura_y_la_migracion_es_append_only():
    rutas = Path("app/routes/audit_routes.py").read_text(encoding="utf-8")
    migracion = Path("alembic/versions/0015_business_audit_log.py").read_text(encoding="utf-8")

    assert '@router.get("")' in rutas
    assert '@router.get("/{evento_id}")' in rutas
    assert "@router.post" not in rutas
    assert "@router.put" not in rutas
    assert "@router.patch" not in rutas
    assert "@router.delete" not in rutas
    assert "BEFORE UPDATE OR DELETE ON audit_events" in migracion

"""
Pruebas del módulo Reservaciones. SQLite en memoria, igual que
Clientes. Los clientes/servicios/usuarios de prueba se insertan
directo con el ORM (no vía API) porque los módulos Servicios y
Auth/Usuarios todavía no tienen rutas propias.

Correr con:
    pytest tests/test_reservaciones.py -v
"""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.cliente import Cliente
from app.models.reservacion import Reservacion  # noqa: F401
from app.models.servicio import Servicio
from app.models.usuario import Rol, Usuario


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    session = TestingSessionLocal()
    yield session
    session.close()
    app.dependency_overrides.clear()


@pytest.fixture()
def client(db_session):
    """
    Cliente HTTP autenticado por defecto (las rutas ahora exigen JWT).
    """
    from app.core.security import create_access_token

    rol = Rol(nombre="admin", descripcion="Admin de prueba")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Usuario Test",
        email="test-reservaciones@ejixhole.com",
        password_hash="no-se-usa-en-estos-tests",
        rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    token = create_access_token(subject=usuario.email, rol=rol.nombre)

    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture()
def setup_basico(db_session):
    """Crea un rol, un usuario, un cliente y un servicio listos para reservar."""
    rol = Rol(nombre="operador", descripcion="Operador de recepción")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)

    usuario = Usuario(
        nombre="Recepcionista Test",
        email="recepcion@test.com",
        password_hash="hash-falso-no-se-usa-en-estos-tests",
        rol_id=rol.id,
    )
    db_session.add(usuario)

    cliente = Cliente(nombre="Cliente Test", telefono="5550001111")
    db_session.add(cliente)

    servicio = Servicio(
        nombre="Acceso al parque", precio="50.00", capacidad_maxima=10, categoria="entrada", reservable=True
    )
    db_session.add(servicio)

    db_session.commit()
    db_session.refresh(usuario)
    db_session.refresh(cliente)
    db_session.refresh(servicio)

    return {"usuario": usuario, "cliente": cliente, "servicio": servicio}


def _payload(setup_basico, **overrides):
    base = {
        "cliente_id": setup_basico["cliente"].id,
        "servicio_id": setup_basico["servicio"].id,
        "usuario_id": setup_basico["usuario"].id,
        "tipo_reservacion": "entrada",
        "fecha_llegada": "2026-08-15",
        "fecha_salida": "2026-08-15",
        "num_personas": 4,
        "origen": "recepcion",
    }
    base.update(overrides)
    return base


def test_crear_reservacion(client, setup_basico):
    response = client.post("/reservaciones", json=_payload(setup_basico))

    assert response.status_code == 201
    data = response.json()
    assert data["estado"] == "pendiente"
    assert data["total"] == "200.00"  # $50 entrada x 4 personas (1 día)
    assert data["saldo_pendiente"] == "200.00"


def test_crear_reservacion_cliente_inexistente(client, setup_basico):
    response = client.post("/reservaciones", json=_payload(setup_basico, cliente_id=9999))
    assert response.status_code == 404


def test_crear_reservacion_servicio_inexistente(client, setup_basico):
    response = client.post("/reservaciones", json=_payload(setup_basico, servicio_id=9999))
    assert response.status_code == 404


def test_crear_reservacion_excede_capacidad(client, setup_basico):
    response = client.post("/reservaciones", json=_payload(setup_basico, num_personas=99))
    assert response.status_code == 400
    assert "capacidad" in response.json()["detail"].lower() or "personas" in response.json()["detail"].lower()


def test_cliente_puede_tener_varias_reservaciones_activas(client, setup_basico):
    """
    Reemplaza test_una_reservacion_activa_por_cliente (removido):
    decisión explícita del negocio, ver docs/portal-publico-fase-1.md.
    Un cliente ahora SÍ puede tener varias reservaciones pendientes o
    confirmadas al mismo tiempo — el sistema confía en que el contacto
    real del cliente (teléfono/email) permite resolver cualquier
    choque manualmente en vez de bloquearlo por regla.
    """
    primera = client.post("/reservaciones", json=_payload(setup_basico))
    assert primera.status_code == 201
    assert primera.json()["estado"] == "pendiente"

    segunda = client.post(
        "/reservaciones",
        json=_payload(setup_basico, fecha_llegada="2026-09-01", fecha_salida="2026-09-01"),
    )
    assert segunda.status_code == 201
    assert segunda.json()["estado"] == "pendiente"

    # Ambas conviven activas — antes, la segunda hubiera dado 409.
    todas = client.get("/reservaciones", params={"cliente_id": setup_basico["cliente"].id}).json()
    assert len(todas) == 2


def test_nueva_reservacion_permitida_tras_cancelar_la_anterior(client, setup_basico):
    primera = client.post("/reservaciones", json=_payload(setup_basico)).json()

    cancelada = client.patch(
        f"/reservaciones/{primera['id']}/estado", json={"nuevo_estado": "cancelada"}
    )
    assert cancelada.status_code == 200

    segunda = client.post(
        "/reservaciones",
        json=_payload(setup_basico, fecha_llegada="2026-09-01", fecha_salida="2026-09-01"),
    )
    assert segunda.status_code == 201


def test_cambiar_estado_a_confirmada(client, setup_basico):
    creada = client.post("/reservaciones", json=_payload(setup_basico)).json()

    response = client.patch(
        f"/reservaciones/{creada['id']}/estado", json={"nuevo_estado": "confirmada"}
    )

    assert response.status_code == 200
    assert response.json()["estado"] == "confirmada"


def test_no_se_puede_cambiar_estado_de_reservacion_terminal(client, setup_basico):
    creada = client.post("/reservaciones", json=_payload(setup_basico)).json()
    client.patch(f"/reservaciones/{creada['id']}/estado", json={"nuevo_estado": "cancelada"})

    response = client.patch(
        f"/reservaciones/{creada['id']}/estado", json={"nuevo_estado": "confirmada"}
    )

    assert response.status_code == 409


def test_obtener_reservacion_inexistente_da_404(client, setup_basico):
    response = client.get("/reservaciones/9999")
    assert response.status_code == 404


def test_listar_reservaciones_filtra_por_estado(client, setup_basico):
    creada = client.post("/reservaciones", json=_payload(setup_basico)).json()
    client.patch(f"/reservaciones/{creada['id']}/estado", json={"nuevo_estado": "confirmada"})

    pendientes = client.get("/reservaciones", params={"estado": "pendiente"}).json()
    confirmadas = client.get("/reservaciones", params={"estado": "confirmada"}).json()

    assert len(pendientes) == 0
    assert len(confirmadas) == 1


def test_no_se_puede_reservar_para_cliente_desactivado(client, setup_basico, db_session):
    cliente = setup_basico["cliente"]
    cliente.activo = False
    db_session.commit()

    response = client.post("/reservaciones", json=_payload(setup_basico))

    assert response.status_code == 400


# --- Editar reservación (PUT /reservaciones/{id}) ---------------------


def test_editar_num_personas_recalcula_total(client, setup_basico):
    creada = client.post("/reservaciones", json=_payload(setup_basico)).json()
    assert creada["total"] == "200.00"  # $50 x 4 personas

    response = client.put(f"/reservaciones/{creada['id']}", json={"num_personas": 2})

    assert response.status_code == 200
    data = response.json()
    assert data["num_personas"] == 2
    assert data["total"] == "100.00"  # $50 x 2 personas


def test_editar_fechas_reservacion_entrada(client, setup_basico):
    creada = client.post("/reservaciones", json=_payload(setup_basico)).json()

    response = client.put(
        f"/reservaciones/{creada['id']}",
        json={"fecha_llegada": "2026-09-01", "fecha_salida": "2026-09-01"},
    )

    assert response.status_code == 200
    assert response.json()["fecha_llegada"] == "2026-09-01"


def test_editar_reservacion_entrada_con_fechas_distintas_rechazado(client, setup_basico):
    creada = client.post("/reservaciones", json=_payload(setup_basico)).json()

    response = client.put(
        f"/reservaciones/{creada['id']}",
        json={"fecha_llegada": "2026-09-01", "fecha_salida": "2026-09-03"},
    )

    assert response.status_code == 400


def test_editar_reservacion_inexistente_404(client, setup_basico):
    response = client.put("/reservaciones/9999", json={"num_personas": 2})
    assert response.status_code == 404


def test_editar_reservacion_terminal_rechazado_409(client, setup_basico):
    creada = client.post("/reservaciones", json=_payload(setup_basico)).json()
    client.patch(f"/reservaciones/{creada['id']}/estado", json={"nuevo_estado": "cancelada"})

    response = client.put(f"/reservaciones/{creada['id']}", json={"num_personas": 2})

    assert response.status_code == 409


def test_editar_reservacion_no_puede_bajar_el_total_bajo_lo_pagado(client, setup_basico, db_session):
    creada = client.post("/reservaciones", json=_payload(setup_basico)).json()

    reservacion = db_session.query(Reservacion).filter(Reservacion.id == creada["id"]).first()
    reservacion.monto_pagado = "150.00"  # de los $200 originales
    db_session.commit()

    # Bajar a 2 personas dejaría el total en $100 — menos de lo ya pagado.
    response = client.put(f"/reservaciones/{creada['id']}", json={"num_personas": 2})

    assert response.status_code == 409


def test_editar_reservacion_servicio_inexistente_404(client, setup_basico):
    creada = client.post("/reservaciones", json=_payload(setup_basico)).json()

    response = client.put(f"/reservaciones/{creada['id']}", json={"servicio_id": 9999})

    assert response.status_code == 404


def test_editar_reservacion_excede_capacidad(client, setup_basico):
    creada = client.post("/reservaciones", json=_payload(setup_basico)).json()

    response = client.put(f"/reservaciones/{creada['id']}", json={"num_personas": 99})

    assert response.status_code == 400


def test_editar_reservacion_sin_cambios_no_falla(client, setup_basico):
    """PUT con body vacío no debe romper nada — conserva todos los valores actuales."""
    creada = client.post("/reservaciones", json=_payload(setup_basico)).json()

    response = client.put(f"/reservaciones/{creada['id']}", json={})

    assert response.status_code == 200
    assert response.json()["total"] == creada["total"]



def test_operador_puede_listar_reservaciones(db_session):
    rol = Rol(nombre="operador", descripcion="Operador")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Operador Permiso", email="operador-permiso-reservaciones@ejixhole.com",
        password_hash="x", rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    from app.core.security import create_access_token
    token = create_access_token(subject=usuario.email, rol=rol.nombre)

    response = TestClient(app, headers={"Authorization": f"Bearer {token}"}).get("/reservaciones")
    assert response.status_code == 200


def test_cajero_no_puede_acceder_a_reservaciones(db_session):
    rol = Rol(nombre="cajero", descripcion="Cajero")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Cajero Permiso", email="cajero-permiso-reservaciones@ejixhole.com",
        password_hash="x", rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    from app.core.security import create_access_token
    token = create_access_token(subject=usuario.email, rol=rol.nombre)

    response = TestClient(app, headers={"Authorization": f"Bearer {token}"}).get("/reservaciones")
    assert response.status_code == 403


# --- Portal público: tipos de reservación, precios y disponibilidad --


@pytest.fixture()
def setup_hospedaje(db_session, setup_basico):
    """Agrega una UnidadHospedaje real (Cabaña 1) al fixture básico."""
    from app.models.unidad_hospedaje import UnidadHospedaje

    unidad = UnidadHospedaje(nombre="Cabaña 1", capacidad_maxima=4, precio_por_noche="800.00")
    db_session.add(unidad)
    db_session.commit()
    db_session.refresh(unidad)
    setup_basico["unidad"] = unidad
    return setup_basico


def test_precio_camping_incluye_entrada(client, setup_basico, db_session):
    from app.models.servicio import Servicio

    camping = Servicio(nombre="Camping", precio="100.00", reservable=True)
    db_session.add(camping)
    db_session.commit()
    db_session.refresh(camping)

    payload = _payload(
        setup_basico,
        servicio_id=camping.id,
        tipo_reservacion="camping",
        fecha_llegada="2026-08-15",
        fecha_salida="2026-08-17",  # 2 noches
        num_personas=3,
    )
    response = client.post("/reservaciones", json=payload)

    assert response.status_code == 201
    # (50 entrada + 100 camping) x 3 personas x 2 noches = 900
    assert response.json()["total"] == "900.00"


def test_precio_hospedaje_es_precio_fijo_por_unidad(client, setup_hospedaje):
    payload = _payload(
        setup_hospedaje,
        tipo_reservacion="hospedaje",
        unidad_hospedaje_id=setup_hospedaje["unidad"].id,
        fecha_llegada="2026-08-15",
        fecha_salida="2026-08-18",  # 3 noches
        num_personas=4,
    )
    response = client.post("/reservaciones", json=payload)

    assert response.status_code == 201
    # (50 entrada x 4 personas x 3 noches) + (800 x 3 noches) = 600 + 2400 = 3000
    assert response.json()["total"] == "3000.00"


def test_hospedaje_rechaza_traslape_de_fechas(client, setup_hospedaje):
    primera = client.post(
        "/reservaciones",
        json=_payload(
            setup_hospedaje,
            tipo_reservacion="hospedaje",
            unidad_hospedaje_id=setup_hospedaje["unidad"].id,
            fecha_llegada="2026-08-15",
            fecha_salida="2026-08-18",
        ),
    )
    assert primera.status_code == 201

    # Se traslapa (16-17 cae dentro de 15-18)
    segunda = client.post(
        "/reservaciones",
        json=_payload(
            setup_hospedaje,
            tipo_reservacion="hospedaje",
            unidad_hospedaje_id=setup_hospedaje["unidad"].id,
            fecha_llegada="2026-08-16",
            fecha_salida="2026-08-17",
        ),
    )
    assert segunda.status_code == 409


def test_hospedaje_misma_unidad_fechas_consecutivas_si_se_permite(client, setup_hospedaje):
    """Salida exclusiva: alguien puede llegar el mismo día que otro se va."""
    primera = client.post(
        "/reservaciones",
        json=_payload(
            setup_hospedaje,
            tipo_reservacion="hospedaje",
            unidad_hospedaje_id=setup_hospedaje["unidad"].id,
            fecha_llegada="2026-08-15",
            fecha_salida="2026-08-18",
        ),
    )
    assert primera.status_code == 201

    consecutiva = client.post(
        "/reservaciones",
        json=_payload(
            setup_hospedaje,
            tipo_reservacion="hospedaje",
            unidad_hospedaje_id=setup_hospedaje["unidad"].id,
            fecha_llegada="2026-08-18",
            fecha_salida="2026-08-20",
        ),
    )
    assert consecutiva.status_code == 201


def test_entrada_exige_llegada_y_salida_mismo_dia(client, setup_basico):
    response = client.post(
        "/reservaciones",
        json=_payload(setup_basico, tipo_reservacion="entrada", fecha_llegada="2026-08-15", fecha_salida="2026-08-16"),
    )
    assert response.status_code == 422


def test_hospedaje_exige_unidad_hospedaje_id(client, setup_basico):
    response = client.post(
        "/reservaciones",
        json=_payload(
            setup_basico,
            tipo_reservacion="hospedaje",
            fecha_llegada="2026-08-15",
            fecha_salida="2026-08-16",
        ),
    )
    assert response.status_code == 422


def test_entrada_no_admite_unidad_hospedaje_id(client, setup_hospedaje):
    response = client.post(
        "/reservaciones",
        json=_payload(setup_hospedaje, tipo_reservacion="entrada", unidad_hospedaje_id=setup_hospedaje["unidad"].id),
    )
    assert response.status_code == 422


# --- CR-02: traducción real del constraint EXCLUDE a 409 --------------
# SQLite (usado en estos tests) no soporta EXCLUDE USING gist — es
# exclusivo de PostgreSQL, así que la migración real
# (0005_no_traslape_hospedaje) no se puede ejercitar aquí de
# punta a punta. Lo que sí se prueba: que si la base de datos llega a
# rechazar por ese constraint específico, el service lo traduce a un
# 409 claro y hace rollback — no un 500 genérico.


def test_guardar_o_409_traduce_violacion_real_del_constraint(db_session):
    from sqlalchemy.exc import IntegrityError

    from app.services.reservacion_service import ReservacionService

    service = ReservacionService(db_session)

    class _ErrorOriginalFalso:
        def __str__(self):
            return 'llave duplicada viola restricción de unicidad «ck_no_traslape_unidad_hospedaje»'

    def _operacion_que_falla():
        raise IntegrityError("statement", "params", _ErrorOriginalFalso())

    with pytest.raises(HTTPException) as exc_info:
        service._guardar_o_409(_operacion_que_falla)

    assert exc_info.value.status_code == 409
    assert "traslapa" in exc_info.value.detail


def test_guardar_o_409_no_traduce_otros_integrity_error(db_session):
    """Un IntegrityError que NO es del constraint de traslape debe
    seguir propagándose tal cual — no ocultar otros errores reales
    detrás de un 409 que no les corresponde."""
    from sqlalchemy.exc import IntegrityError

    from app.services.reservacion_service import ReservacionService

    service = ReservacionService(db_session)

    class _OtroErrorFalso:
        def __str__(self):
            return "violates foreign key constraint ck_otra_cosa"

    def _operacion_que_falla():
        raise IntegrityError("statement", "params", _OtroErrorFalso())

    with pytest.raises(IntegrityError):
        service._guardar_o_409(_operacion_que_falla)

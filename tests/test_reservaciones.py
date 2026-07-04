"""
Pruebas del módulo Reservaciones. SQLite en memoria, igual que
Clientes. Los clientes/servicios/usuarios de prueba se insertan
directo con el ORM (no vía API) porque los módulos Servicios y
Auth/Usuarios todavía no tienen rutas propias.

Correr con:
    pytest tests/test_reservaciones.py -v
"""
import pytest
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
    return TestClient(app)


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

    servicio = Servicio(nombre="Tour Huasteca", precio="500.00", capacidad_maxima=10)
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
        "fecha_visita": "2026-08-15",
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
    assert data["total"] == "2000.00"  # 500 * 4
    assert data["saldo_pendiente"] == "2000.00"


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


def test_una_reservacion_activa_por_cliente(client, setup_basico):
    primera = client.post("/reservaciones", json=_payload(setup_basico))
    assert primera.status_code == 201

    segunda = client.post("/reservaciones", json=_payload(setup_basico, fecha_visita="2026-09-01"))
    assert segunda.status_code == 409


def test_nueva_reservacion_permitida_tras_cancelar_la_anterior(client, setup_basico):
    primera = client.post("/reservaciones", json=_payload(setup_basico)).json()

    cancelada = client.patch(
        f"/reservaciones/{primera['id']}/estado", json={"nuevo_estado": "cancelada"}
    )
    assert cancelada.status_code == 200

    segunda = client.post("/reservaciones", json=_payload(setup_basico, fecha_visita="2026-09-01"))
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

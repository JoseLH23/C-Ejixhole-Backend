"""
Pruebas del portal público. A diferencia de los demás módulos, aquí el
cliente HTTP NO lleva token — estas rutas son las únicas del backend
sin autenticación, a propósito (las usa el visitante, no el personal).

Correr con:
    pytest tests/test_publico.py -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.servicio import Servicio
from app.models.unidad_hospedaje import UnidadHospedaje


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
    """Sin token — así deben poder usarse las rutas públicas."""
    return TestClient(app)


@pytest.fixture()
def catalogo(db_session):
    """Replica el catálogo real mínimo: los 3 servicios reservables + 1 informativo + 1 unidad."""
    entrada = Servicio(nombre="Acceso al parque", precio="50.00", categoria="entrada", reservable=True)
    camping = Servicio(nombre="Camping", precio="100.00", categoria="camping", reservable=True)
    cabanas = Servicio(nombre="Cabañas", precio="800.00", categoria="hospedaje", reservable=True)
    informativo = Servicio(nombre="Snorkel", precio="0.00", categoria="informativo", reservable=False)
    unidad = UnidadHospedaje(nombre="Cabaña 1", tipo_unidad="cabana", capacidad_maxima=4, precio_por_noche="800.00")

    db_session.add_all([entrada, camping, cabanas, informativo, unidad])
    db_session.commit()
    db_session.refresh(unidad)

    return {"unidad": unidad}


def _payload(**overrides):
    base = {
        "nombre_completo": "Ana Pérez",
        "email": "ana@example.com",
        "telefono": "4441234567",
        "tipo_reservacion": "entrada",
        "fecha_llegada": "2026-08-15",
        "fecha_salida": "2026-08-15",
        "num_personas": 2,
    }
    base.update(overrides)
    return base


def test_listar_servicios_informativos_no_requiere_auth(client, catalogo):
    response = client.get("/publico/servicios")
    assert response.status_code == 200
    nombres = [s["nombre"] for s in response.json()]
    assert nombres == ["Snorkel"]  # solo el informativo, no los 3 reservables


def test_listar_unidades_hospedaje(client, catalogo):
    response = client.get("/publico/unidades-hospedaje")
    assert response.status_code == 200
    assert response.json()[0]["nombre"] == "Cabaña 1"


def test_crear_solicitud_entrada(client, catalogo):
    response = client.post("/publico/reservaciones", json=_payload())
    assert response.status_code == 201
    data = response.json()
    assert data["estado"] == "pendiente"
    assert data["total"] == "100.00"  # 50 x 2 personas
    assert "mensaje" in data
    # No debe exponer detalles internos:
    assert "servicio_id" not in data
    assert "usuario_id" not in data
    assert "cliente_id" not in data


def test_crear_solicitud_reutiliza_cliente_existente(client, catalogo, db_session):
    from app.models.cliente import Cliente

    primera = client.post("/publico/reservaciones", json=_payload())
    assert primera.status_code == 201

    segunda = client.post(
        "/publico/reservaciones",
        json=_payload(fecha_llegada="2026-09-01", fecha_salida="2026-09-01"),
    )
    assert segunda.status_code == 201

    assert db_session.query(Cliente).count() == 1


def test_crear_solicitud_camping(client, catalogo):
    response = client.post(
        "/publico/reservaciones",
        json=_payload(tipo_reservacion="camping", fecha_llegada="2026-08-15", fecha_salida="2026-08-17", num_personas=3),
    )
    assert response.status_code == 201
    assert response.json()["total"] == "900.00"


def test_crear_solicitud_hospedaje(client, catalogo):
    response = client.post(
        "/publico/reservaciones",
        json=_payload(
            tipo_reservacion="hospedaje",
            unidad_hospedaje_id=catalogo["unidad"].id,
            fecha_llegada="2026-08-15",
            fecha_salida="2026-08-18",
            num_personas=4,
        ),
    )
    assert response.status_code == 201
    assert response.json()["total"] == "3000.00"


def test_disponibilidad_libre_y_ocupada(client, catalogo):
    unidad_id = catalogo["unidad"].id

    libre = client.get(
        "/publico/disponibilidad",
        params={"unidad_hospedaje_id": unidad_id, "fecha_llegada": "2026-08-15", "fecha_salida": "2026-08-18"},
    )
    assert libre.json()["disponible"] is True

    client.post(
        "/publico/reservaciones",
        json=_payload(
            tipo_reservacion="hospedaje",
            unidad_hospedaje_id=unidad_id,
            fecha_llegada="2026-08-15",
            fecha_salida="2026-08-18",
            num_personas=2,
        ),
    )

    ocupada = client.get(
        "/publico/disponibilidad",
        params={"unidad_hospedaje_id": unidad_id, "fecha_llegada": "2026-08-16", "fecha_salida": "2026-08-17"},
    )
    assert ocupada.json()["disponible"] is False


def test_solicitud_hospedaje_ocupado_es_rechazada_al_crear(client, catalogo):
    unidad_id = catalogo["unidad"].id
    primera = client.post(
        "/publico/reservaciones",
        json=_payload(
            tipo_reservacion="hospedaje",
            unidad_hospedaje_id=unidad_id,
            fecha_llegada="2026-08-15",
            fecha_salida="2026-08-18",
        ),
    )
    assert primera.status_code == 201

    segunda = client.post(
        "/publico/reservaciones",
        json=_payload(
            tipo_reservacion="hospedaje",
            unidad_hospedaje_id=unidad_id,
            fecha_llegada="2026-08-16",
            fecha_salida="2026-08-17",
        ),
    )
    assert segunda.status_code == 409


def test_email_invalido_es_rechazado(client, catalogo):
    response = client.post("/publico/reservaciones", json=_payload(email="no-es-un-correo"))
    assert response.status_code == 422


def test_crea_la_reservacion_aunque_smtp_no_este_configurado(client, catalogo):
    """Confirma la degradación diseñada: sin SMTP, la reservación se crea igual."""
    response = client.post("/publico/reservaciones", json=_payload())
    assert response.status_code == 201


def test_cotizar_hospedaje_devuelve_desglose_que_suma_el_total(client, catalogo):
    response = client.get(
        "/publico/cotizar",
        params={
            "tipo_reservacion": "hospedaje",
            "unidad_hospedaje_id": catalogo["unidad"].id,
            "fecha_llegada": "2026-08-15",
            "fecha_salida": "2026-08-18",
            "num_personas": 4,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["desglose"]) == 2  # Entrada + Cabaña 1
    suma = sum(float(item["subtotal"]) for item in data["desglose"])
    assert suma == float(data["total"])
    assert data["desglose"][0]["concepto"] == "Entrada al parque"
    assert data["desglose"][1]["concepto"] == "Cabaña 1"


def test_cotizar_entrada_no_crea_nada(client, catalogo, db_session):
    from app.models.reservacion import Reservacion

    response = client.get(
        "/publico/cotizar",
        params={
            "tipo_reservacion": "entrada",
            "fecha_llegada": "2026-08-15",
            "fecha_salida": "2026-08-15",
            "num_personas": 2,
        },
    )
    assert response.status_code == 200
    assert response.json()["total"] == "100.00"
    assert db_session.query(Reservacion).count() == 0  # solo cotizó, no creó


def test_cotizar_hospedaje_mismo_total_que_al_crear(client, catalogo):
    params = {
        "tipo_reservacion": "hospedaje",
        "unidad_hospedaje_id": catalogo["unidad"].id,
        "fecha_llegada": "2026-08-15",
        "fecha_salida": "2026-08-18",
        "num_personas": 4,
    }

    cotizacion = client.get("/publico/cotizar", params=params)
    assert cotizacion.json()["total"] == "3000.00"
    assert cotizacion.json()["noches"] == 3

    creada = client.post("/publico/reservaciones", json=_payload(**params))
    assert creada.json()["total"] == cotizacion.json()["total"]


def test_cotizar_unidad_ocupada_da_409(client, catalogo):
    unidad_id = catalogo["unidad"].id
    client.post(
        "/publico/reservaciones",
        json=_payload(
            tipo_reservacion="hospedaje",
            unidad_hospedaje_id=unidad_id,
            fecha_llegada="2026-08-15",
            fecha_salida="2026-08-18",
        ),
    )

    response = client.get(
        "/publico/cotizar",
        params={
            "tipo_reservacion": "hospedaje",
            "unidad_hospedaje_id": unidad_id,
            "fecha_llegada": "2026-08-16",
            "fecha_salida": "2026-08-17",
            "num_personas": 2,
        },
    )
    assert response.status_code == 409


# --- ME-11: la categoría ya no depende del nombre visible ------------------


def test_renombrar_la_unidad_no_cambia_la_categoria_resuelta(client, db_session, catalogo):
    """Antes de este fix, esto habría fallado: la lógica leía
    nombre.startswith("Cabañ"). Ahora usa tipo_unidad, así que un
    nombre que NO empieza con "Cabañ" sigue resolviendo bien si su
    tipo_unidad='cabana' real."""
    unidad = catalogo["unidad"]
    unidad.nombre = "Suite Vista al Río"  # ya no empieza con "Cabañ"
    db_session.commit()

    response = client.post(
        "/publico/reservaciones",
        json=_payload(
            tipo_reservacion="hospedaje",
            unidad_hospedaje_id=unidad.id,
            fecha_llegada="2026-08-20",
            fecha_salida="2026-08-22",
        ),
    )

    assert response.status_code == 201  # sigue resolviendo la categoría "Cabañas" bien


# --- AL-05: no reutilizar cliente por coincidencia parcial ----------------


def test_telefono_compartido_con_correo_distinto_no_reutiliza_cliente(client, db_session, catalogo):
    """Dos personas con el mismo teléfono (familia, oficina) no deben
    terminar compartiendo el mismo registro de cliente solo porque
    coincide un dato."""
    from app.models.reservacion import Reservacion

    r1 = client.post(
        "/publico/reservaciones",
        json=_payload(email="persona.a@example.com", telefono="4441112222"),
    )
    r2 = client.post(
        "/publico/reservaciones",
        json=_payload(email="persona.b@example.com", telefono="4441112222"),  # mismo teléfono
    )

    assert r1.status_code == 201 and r2.status_code == 201
    reservacion_1 = db_session.query(Reservacion).filter(Reservacion.id == r1.json()["id"]).first()
    reservacion_2 = db_session.query(Reservacion).filter(Reservacion.id == r2.json()["id"]).first()
    assert reservacion_1.cliente_id != reservacion_2.cliente_id


def test_mismo_telefono_y_correo_si_reutiliza_al_cliente_recurrente(client, db_session, catalogo):
    from app.models.reservacion import Reservacion

    r1 = client.post(
        "/publico/reservaciones",
        json=_payload(email="recurrente@example.com", telefono="4443334444", fecha_llegada="2026-09-01", fecha_salida="2026-09-01"),
    )
    r2 = client.post(
        "/publico/reservaciones",
        json=_payload(email="recurrente@example.com", telefono="4443334444", fecha_llegada="2026-09-05", fecha_salida="2026-09-05"),
    )

    reservacion_1 = db_session.query(Reservacion).filter(Reservacion.id == r1.json()["id"]).first()
    reservacion_2 = db_session.query(Reservacion).filter(Reservacion.id == r2.json()["id"]).first()
    assert reservacion_1.cliente_id == reservacion_2.cliente_id

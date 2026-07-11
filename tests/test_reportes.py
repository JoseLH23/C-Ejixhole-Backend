"""
Pruebas de la primera entrega del módulo Reportes: /reportes/ingresos
y /reportes/cuentas-por-cobrar. Mismo patrón de SQLite en memoria que
los demás módulos.

Los pagos y reservaciones de prueba se insertan directo por ORM (no
vía API) porque necesitamos controlar fechas históricas exactas
(fecha_pago, fecha_creacion) para probar agrupación por periodo y
antigüedad — la API no expone esos campos para escritura manual.

Correr con:
    pytest tests/test_reportes.py -v
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models.cliente import Cliente
from app.models.pago import Pago
from app.models.reservacion import Reservacion
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
    """Cliente HTTP autenticado con rol admin (Reportes exige exactamente ese rol)."""
    rol = Rol(nombre="admin", descripcion="Admin de prueba")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Admin Test",
        email="admin-reportes@ejixhole.com",
        password_hash="no-se-usa-en-estos-tests",
        rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    token = create_access_token(subject=usuario.email, rol=rol.nombre)

    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture()
def client_no_admin(db_session):
    """Cliente HTTP autenticado pero SIN rol admin — para probar el 403."""
    rol = Rol(nombre="operador_reportes_test", descripcion="Operador")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Operador Test",
        email="operador-reportes@ejixhole.com",
        password_hash="no-se-usa-en-estos-tests",
        rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    token = create_access_token(subject=usuario.email, rol=rol.nombre)

    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture()
def base(db_session):
    """Un usuario de negocio, un cliente y un servicio, listos para crear reservaciones/pagos."""
    rol = Rol(nombre="cajero_reportes_test", descripcion="Cajero")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)

    usuario = Usuario(
        nombre="Cajero Reportes",
        email="cajero-reportes@ejixhole.com",
        password_hash="hash-falso",
        rol_id=rol.id,
    )
    cliente = Cliente(nombre="Cliente Reportes Test")
    servicio = Servicio(nombre="Tour Reportes", precio=Decimal("500.00"), capacidad_maxima=10)
    db_session.add_all([usuario, cliente, servicio])
    db_session.commit()
    db_session.refresh(usuario)
    db_session.refresh(cliente)
    db_session.refresh(servicio)

    return {"usuario": usuario, "cliente": cliente, "servicio": servicio}


def _crear_cliente_extra(db_session, nombre):
    """
    Cliente adicional para tests que necesitan varias reservaciones
    activas simultáneas en Reportes. Ya no es obligatorio usar un
    cliente distinto por reservación (la regla de "una activa por
    cliente" se eliminó — ver docs/portal-publico-fase-1.md), pero se
    conserva este helper para no reescribir los tests existentes que
    ya lo usan así.
    """
    cliente = Cliente(nombre=nombre)
    db_session.add(cliente)
    db_session.commit()
    db_session.refresh(cliente)
    return cliente


def _crear_reservacion(
    db_session, base, total=Decimal("1000.00"), monto_pagado=Decimal("0"), estado="pendiente",
    fecha_creacion=None, fecha_visita=None, num_personas=2, origen="recepcion",
):
    reservacion = Reservacion(
        cliente_id=base["cliente"].id,
        servicio_id=base["servicio"].id,
        usuario_id=base["usuario"].id,
        fecha_visita=fecha_visita or date(2026, 8, 15),
        num_personas=num_personas,
        origen=origen,
        total=total,
        monto_pagado=monto_pagado,
        estado=estado,
    )
    if fecha_creacion is not None:
        reservacion.fecha_creacion = fecha_creacion
    db_session.add(reservacion)
    db_session.commit()
    db_session.refresh(reservacion)
    return reservacion


def _crear_pago(db_session, reservacion, base, monto, tipo="pago_completo", metodo_pago="efectivo", fecha_pago=None):
    pago = Pago(
        reservacion_id=reservacion.id,
        usuario_id=base["usuario"].id,
        monto=monto,
        tipo=tipo,
        metodo_pago=metodo_pago,
    )
    if fecha_pago is not None:
        pago.fecha_pago = fecha_pago
    db_session.add(pago)
    db_session.commit()
    db_session.refresh(pago)
    return pago


# --- Autenticación / autorización -----------------------------------


def test_ingresos_sin_token_da_401():
    response = TestClient(app).get("/reportes/ingresos")
    assert response.status_code == 401


def test_ingresos_requiere_admin(client_no_admin):
    response = client_no_admin.get("/reportes/ingresos")
    assert response.status_code == 403


def test_cuentas_por_cobrar_requiere_admin(client_no_admin):
    response = client_no_admin.get("/reportes/cuentas-por-cobrar")
    assert response.status_code == 403


# --- /reportes/ingresos ----------------------------------------------


def test_ingresos_agrupado_por_dia(client, db_session, base):
    r1 = _crear_reservacion(db_session, base, total=Decimal("1000.00"))
    _crear_pago(
        db_session, r1, base, Decimal("300.00"),
        fecha_pago=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
    )
    _crear_pago(
        db_session, r1, base, Decimal("200.00"),
        fecha_pago=datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc),
    )

    response = client.get(
        "/reportes/ingresos", params={"desde": "2026-07-01", "hasta": "2026-07-31"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["num_pagos"] == 2
    assert data["total_ingresos"] == "500.00"
    assert data["total_neto"] == "500.00"
    assert len(data["serie"]) == 2
    assert data["serie"][0]["periodo"] == "2026-07-01"
    assert data["serie"][0]["ingresos"] == "300.00"
    assert data["serie"][1]["periodo"] == "2026-07-02"
    assert data["serie"][1]["ingresos"] == "200.00"


def test_ingresos_agrupado_por_mes(client, db_session, base):
    r1 = _crear_reservacion(db_session, base)
    _crear_pago(
        db_session, r1, base, Decimal("100.00"),
        fecha_pago=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    _crear_pago(
        db_session, r1, base, Decimal("400.00"),
        fecha_pago=datetime(2026, 7, 20, tzinfo=timezone.utc),
    )
    _crear_pago(
        db_session, r1, base, Decimal("50.00"),
        fecha_pago=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )

    response = client.get(
        "/reportes/ingresos",
        params={"desde": "2026-07-01", "hasta": "2026-08-31", "agrupar_por": "mes"},
    )

    data = response.json()
    assert len(data["serie"]) == 2
    assert data["serie"][0]["periodo"] == "2026-07"
    assert data["serie"][0]["ingresos"] == "500.00"
    assert data["serie"][1]["periodo"] == "2026-08"
    assert data["serie"][1]["ingresos"] == "50.00"


def test_ingresos_resta_reembolsos_del_neto(client, db_session, base):
    r1 = _crear_reservacion(db_session, base)
    _crear_pago(
        db_session, r1, base, Decimal("500.00"), tipo="pago_completo",
        fecha_pago=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    _crear_pago(
        db_session, r1, base, Decimal("100.00"), tipo="reembolso",
        fecha_pago=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )

    response = client.get(
        "/reportes/ingresos", params={"desde": "2026-07-01", "hasta": "2026-07-31"}
    )

    data = response.json()
    assert data["total_ingresos"] == "500.00"
    assert data["total_reembolsos"] == "100.00"
    assert data["total_neto"] == "400.00"


def test_ingresos_filtra_por_metodo_pago(client, db_session, base):
    r1 = _crear_reservacion(db_session, base)
    _crear_pago(
        db_session, r1, base, Decimal("200.00"), metodo_pago="efectivo",
        fecha_pago=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    _crear_pago(
        db_session, r1, base, Decimal("300.00"), metodo_pago="tarjeta",
        fecha_pago=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )

    response = client.get(
        "/reportes/ingresos",
        params={"desde": "2026-07-01", "hasta": "2026-07-31", "metodo_pago": "tarjeta"},
    )

    data = response.json()
    assert data["total_ingresos"] == "300.00"
    assert data["num_pagos"] == 1


def test_ingresos_filtra_por_servicio_id(client, db_session, base):
    otro_servicio = Servicio(nombre="Otro Servicio", precio=Decimal("100.00"))
    db_session.add(otro_servicio)
    db_session.commit()
    db_session.refresh(otro_servicio)

    otro_cliente = _crear_cliente_extra(db_session, "Cliente Reportes Test 2")

    r1 = _crear_reservacion(db_session, base)
    otra_base = dict(base, servicio=otro_servicio, cliente=otro_cliente)
    r2 = _crear_reservacion(db_session, otra_base)

    _crear_pago(db_session, r1, base, Decimal("500.00"), fecha_pago=datetime(2026, 7, 1, tzinfo=timezone.utc))
    _crear_pago(db_session, r2, base, Decimal("100.00"), fecha_pago=datetime(2026, 7, 1, tzinfo=timezone.utc))

    response = client.get(
        "/reportes/ingresos",
        params={"desde": "2026-07-01", "hasta": "2026-07-31", "servicio_id": base["servicio"].id},
    )

    data = response.json()
    assert data["total_ingresos"] == "500.00"
    assert data["num_pagos"] == 1


def test_ingresos_periodo_invalido_da_400(client):
    response = client.get("/reportes/ingresos", params={"periodo": "invalido"})
    assert response.status_code == 400


def test_ingresos_agrupar_por_invalido_da_400(client):
    response = client.get("/reportes/ingresos", params={"agrupar_por": "hora"})
    assert response.status_code == 400


def test_ingresos_desde_mayor_a_hasta_da_400(client):
    response = client.get(
        "/reportes/ingresos", params={"desde": "2026-07-31", "hasta": "2026-07-01"}
    )
    assert response.status_code == 400


def test_ingresos_periodo_hoy_ignora_pagos_de_otros_dias(client, db_session, base):
    hoy = datetime.now(timezone.utc)
    r1 = _crear_reservacion(db_session, base)
    _crear_pago(db_session, r1, base, Decimal("999.00"), fecha_pago=datetime(2020, 1, 1, tzinfo=timezone.utc))
    _crear_pago(db_session, r1, base, Decimal("77.00"), fecha_pago=hoy)

    response = client.get("/reportes/ingresos", params={"periodo": "hoy"})

    data = response.json()
    assert data["total_ingresos"] == "77.00"


# --- /reportes/cuentas-por-cobrar --------------------------------------


def test_cuentas_por_cobrar_lista_reservaciones_con_saldo(client, db_session, base):
    _crear_reservacion(db_session, base, total=Decimal("1000.00"), monto_pagado=Decimal("400.00"))

    response = client.get("/reportes/cuentas-por-cobrar")

    assert response.status_code == 200
    data = response.json()
    assert data["num_reservaciones"] == 1
    assert data["total_pendiente"] == "600.00"
    assert data["items"][0]["saldo_pendiente"] == "600.00"


def test_cuentas_por_cobrar_excluye_reservaciones_totalmente_pagadas(client, db_session, base):
    _crear_reservacion(db_session, base, total=Decimal("500.00"), monto_pagado=Decimal("500.00"))

    response = client.get("/reportes/cuentas-por-cobrar")

    data = response.json()
    assert data["num_reservaciones"] == 0
    assert data["total_pendiente"] == "0"


def test_cuentas_por_cobrar_excluye_reservaciones_canceladas(client, db_session, base):
    _crear_reservacion(
        db_session, base, total=Decimal("500.00"), monto_pagado=Decimal("0"), estado="cancelada"
    )

    response = client.get("/reportes/cuentas-por-cobrar")

    data = response.json()
    assert data["num_reservaciones"] == 0


def test_cuentas_por_cobrar_calcula_antiguedad(client, db_session, base):
    hace_10_dias = datetime.now(timezone.utc) - timedelta(days=10)
    _crear_reservacion(
        db_session, base, total=Decimal("500.00"), monto_pagado=Decimal("0"),
        fecha_creacion=hace_10_dias,
    )

    response = client.get("/reportes/cuentas-por-cobrar")

    data = response.json()
    assert data["items"][0]["antiguedad_dias"] in (9, 10, 11)  # tolerancia por hora exacta


def test_cuentas_por_cobrar_filtra_por_antiguedad_minima(client, db_session, base):
    reciente = datetime.now(timezone.utc) - timedelta(days=1)
    antigua = datetime.now(timezone.utc) - timedelta(days=30)

    cliente_2 = _crear_cliente_extra(db_session, "Cliente Antiguedad 2")
    base_2 = dict(base, cliente=cliente_2)

    _crear_reservacion(
        db_session, base, total=Decimal("100.00"), monto_pagado=Decimal("0"), fecha_creacion=reciente
    )
    _crear_reservacion(
        db_session, base_2, total=Decimal("200.00"), monto_pagado=Decimal("0"), fecha_creacion=antigua
    )

    response = client.get("/reportes/cuentas-por-cobrar", params={"antiguedad_minima_dias": 15})

    data = response.json()
    assert data["num_reservaciones"] == 1
    assert data["items"][0]["saldo_pendiente"] == "200.00"


def test_cuentas_por_cobrar_ordena_por_antiguedad_descendente(client, db_session, base):
    cliente_2 = _crear_cliente_extra(db_session, "Cliente Orden 2")
    base_2 = dict(base, cliente=cliente_2)

    _crear_reservacion(
        db_session, base, total=Decimal("100.00"), monto_pagado=Decimal("0"),
        fecha_creacion=datetime.now(timezone.utc) - timedelta(days=2),
    )
    _crear_reservacion(
        db_session, base_2, total=Decimal("200.00"), monto_pagado=Decimal("0"),
        fecha_creacion=datetime.now(timezone.utc) - timedelta(days=20),
    )

    response = client.get("/reportes/cuentas-por-cobrar")

    data = response.json()
    assert data["items"][0]["antiguedad_dias"] >= data["items"][1]["antiguedad_dias"]


def test_cuentas_por_cobrar_antiguedad_negativa_rechazada(client):
    response = client.get("/reportes/cuentas-por-cobrar", params={"antiguedad_minima_dias": -1})
    assert response.status_code == 400


# =====================================================================
# Entrega 2 — reportes operacionales
# =====================================================================

# --- /reportes/ocupacion ------------------------------------------


def test_ocupacion_calcula_porcentaje_promedio(client, db_session, base):
    # base["servicio"] tiene capacidad_maxima=10
    cliente_2 = _crear_cliente_extra(db_session, "Ocupacion Cliente 2")
    base_2 = dict(base, cliente=cliente_2)

    _crear_reservacion(db_session, base, num_personas=5, fecha_visita=date(2026, 8, 10))
    _crear_reservacion(db_session, base_2, num_personas=10, fecha_visita=date(2026, 8, 20))

    response = client.get(
        "/reportes/ocupacion", params={"desde": "2026-08-01", "hasta": "2026-08-31"}
    )

    assert response.status_code == 200
    items = response.json()["items"]
    item = next(i for i in items if i["servicio_id"] == base["servicio"].id)
    assert item["num_reservaciones"] == 2
    assert item["total_personas"] == 15
    assert item["promedio_personas_por_reservacion"] == 7.5
    assert item["porcentaje_ocupacion_promedio"] == 75.0


def test_ocupacion_excluye_canceladas(client, db_session, base):
    _crear_reservacion(
        db_session, base, num_personas=5, fecha_visita=date(2026, 8, 10), estado="completada"
    )
    _crear_reservacion(
        db_session, base, num_personas=100, fecha_visita=date(2026, 8, 11), estado="cancelada"
    )

    response = client.get(
        "/reportes/ocupacion", params={"desde": "2026-08-01", "hasta": "2026-08-31"}
    )

    item = next(
        i for i in response.json()["items"] if i["servicio_id"] == base["servicio"].id
    )
    assert item["num_reservaciones"] == 1
    assert item["total_personas"] == 5


def test_ocupacion_sin_capacidad_maxima_da_none(client, db_session, base):
    servicio_sin_capacidad = Servicio(nombre="Sin capacidad", precio=Decimal("100.00"))
    db_session.add(servicio_sin_capacidad)
    db_session.commit()
    db_session.refresh(servicio_sin_capacidad)

    base_2 = dict(base, servicio=servicio_sin_capacidad)
    _crear_reservacion(db_session, base_2, num_personas=3, fecha_visita=date(2026, 8, 10))

    response = client.get(
        "/reportes/ocupacion", params={"desde": "2026-08-01", "hasta": "2026-08-31"}
    )

    item = next(
        i for i in response.json()["items"] if i["servicio_id"] == servicio_sin_capacidad.id
    )
    assert item["porcentaje_ocupacion_promedio"] is None


def test_ocupacion_filtra_por_servicio_id(client, db_session, base):
    otro_servicio = Servicio(nombre="Otro", precio=Decimal("50.00"), capacidad_maxima=5)
    db_session.add(otro_servicio)
    db_session.commit()
    db_session.refresh(otro_servicio)

    cliente_2 = _crear_cliente_extra(db_session, "Ocupacion Filtro Cliente 2")
    base_2 = dict(base, servicio=otro_servicio, cliente=cliente_2)
    _crear_reservacion(db_session, base, num_personas=2, fecha_visita=date(2026, 8, 10))
    _crear_reservacion(db_session, base_2, num_personas=2, fecha_visita=date(2026, 8, 10))

    response = client.get(
        "/reportes/ocupacion",
        params={"desde": "2026-08-01", "hasta": "2026-08-31", "servicio_id": base["servicio"].id},
    )

    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["servicio_id"] == base["servicio"].id


def test_ocupacion_fuera_de_rango_no_cuenta(client, db_session, base):
    _crear_reservacion(db_session, base, num_personas=5, fecha_visita=date(2026, 8, 10))

    response = client.get(
        "/reportes/ocupacion", params={"desde": "2026-09-01", "hasta": "2026-09-30"}
    )

    item = next(
        i for i in response.json()["items"] if i["servicio_id"] == base["servicio"].id
    )
    assert item["num_reservaciones"] == 0
    assert item["porcentaje_ocupacion_promedio"] is None


def test_ocupacion_requiere_admin(client_no_admin):
    response = client_no_admin.get("/reportes/ocupacion")
    assert response.status_code == 403


# --- /reportes/servicios-mas-vendidos -------------------------------


def test_servicios_mas_vendidos_ranking(client, db_session, base):
    servicio_b = Servicio(nombre="Servicio B", precio=Decimal("200.00"))
    db_session.add(servicio_b)
    db_session.commit()
    db_session.refresh(servicio_b)

    cliente_2 = _crear_cliente_extra(db_session, "Vendidos Cliente 2")
    cliente_3 = _crear_cliente_extra(db_session, "Vendidos Cliente 3")
    base_2 = dict(base, cliente=cliente_2)
    base_b = dict(base, servicio=servicio_b, cliente=cliente_3)

    _crear_reservacion(db_session, base, total=Decimal("300.00"))
    _crear_reservacion(db_session, base_2, total=Decimal("400.00"))
    _crear_reservacion(db_session, base_b, total=Decimal("150.00"))

    response = client.get("/reportes/servicios-mas-vendidos")

    items = response.json()["items"]
    assert items[0]["servicio_id"] == base["servicio"].id
    assert items[0]["num_reservaciones"] == 2
    assert items[0]["total_facturado"] == "700.00"
    assert items[1]["servicio_id"] == servicio_b.id
    assert items[1]["num_reservaciones"] == 1


def test_servicios_mas_vendidos_excluye_canceladas(client, db_session, base):
    _crear_reservacion(db_session, base, total=Decimal("500.00"), estado="cancelada")

    response = client.get("/reportes/servicios-mas-vendidos")

    items = response.json()["items"]
    assert all(i["servicio_id"] != base["servicio"].id for i in items)


def test_servicios_mas_vendidos_respeta_limit(client, db_session, base):
    clientes_extra = [_crear_cliente_extra(db_session, f"Limit Cliente {i}") for i in range(3)]
    for i in range(3):
        servicio = Servicio(nombre=f"Servicio Limit {i}", precio=Decimal("10.00"))
        db_session.add(servicio)
        db_session.commit()
        db_session.refresh(servicio)
        base_i = dict(base, servicio=servicio, cliente=clientes_extra[i])
        _crear_reservacion(db_session, base_i, total=Decimal("10.00"))

    response = client.get("/reportes/servicios-mas-vendidos", params={"limit": 2})

    assert len(response.json()["items"]) == 2


# --- /reportes/clientes-frecuentes -----------------------------------


def test_clientes_frecuentes_solo_incluye_los_que_cumplen_minimo(client, db_session, base):
    cliente_ocasional = _crear_cliente_extra(db_session, "Ocasional")
    base_ocasional = dict(base, cliente=cliente_ocasional)

    # cliente base: 2 reservaciones históricas (una completada, una pendiente -> no viola la regla)
    _crear_reservacion(db_session, base, total=Decimal("300.00"), estado="completada")
    _crear_reservacion(db_session, base, total=Decimal("200.00"), estado="pendiente")
    # cliente ocasional: solo 1
    _crear_reservacion(db_session, base_ocasional, total=Decimal("150.00"), estado="pendiente")

    response = client.get("/reportes/clientes-frecuentes")

    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["cliente_id"] == base["cliente"].id
    assert items[0]["num_reservaciones"] == 2
    assert items[0]["total_gastado"] == "500.00"


def test_clientes_frecuentes_excluye_canceladas_del_conteo(client, db_session, base):
    _crear_reservacion(db_session, base, total=Decimal("300.00"), estado="completada")
    _crear_reservacion(db_session, base, total=Decimal("200.00"), estado="cancelada")

    response = client.get("/reportes/clientes-frecuentes")

    # solo 1 reservación cuenta (la cancelada no) -> no llega al mínimo de 2
    assert response.json()["items"] == []


def test_clientes_frecuentes_minimo_personalizado(client, db_session, base):
    _crear_reservacion(db_session, base, total=Decimal("150.00"), estado="pendiente")

    response = client.get("/reportes/clientes-frecuentes", params={"minimo_reservaciones": 1})

    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["num_reservaciones"] == 1


def test_clientes_frecuentes_minimo_invalido_rechazado(client):
    response = client.get("/reportes/clientes-frecuentes", params={"minimo_reservaciones": 0})
    assert response.status_code == 400


def test_clientes_frecuentes_respeta_limit(client, db_session, base):
    for i in range(3):
        cliente = _crear_cliente_extra(db_session, f"Frecuente {i}")
        base_i = dict(base, cliente=cliente)
        _crear_reservacion(db_session, base_i, total=Decimal("10.00"), estado="completada")
        _crear_reservacion(db_session, base_i, total=Decimal("10.00"), estado="pendiente")

    response = client.get(
        "/reportes/clientes-frecuentes", params={"limit": 2, "minimo_reservaciones": 2}
    )

    assert len(response.json()["items"]) == 2


# --- /reportes/reservaciones-por-estado -------------------------------


def test_reservaciones_por_estado_cuenta_correctamente(client, db_session, base):
    clientes = [_crear_cliente_extra(db_session, f"Estado {i}") for i in range(4)]
    estados = ("pendiente", "confirmada", "completada", "cancelada")
    for cliente, estado in zip(clientes, estados):
        base_i = dict(base, cliente=cliente)
        _crear_reservacion(db_session, base_i, estado=estado)

    response = client.get("/reportes/reservaciones-por-estado")

    data = response.json()
    assert data["total"] == 4
    assert data["por_estado"] == {
        "pendiente": 1,
        "confirmada": 1,
        "completada": 1,
        "cancelada": 1,
    }


def test_reservaciones_por_estado_filtra_por_servicio_id(client, db_session, base):
    otro_servicio = Servicio(nombre="Otro Estado", precio=Decimal("100.00"))
    db_session.add(otro_servicio)
    db_session.commit()
    db_session.refresh(otro_servicio)

    cliente_2 = _crear_cliente_extra(db_session, "Estado Servicio 2")
    base_2 = dict(base, servicio=otro_servicio, cliente=cliente_2)

    _crear_reservacion(db_session, base, estado="pendiente")
    _crear_reservacion(db_session, base_2, estado="confirmada")

    response = client.get(
        "/reportes/reservaciones-por-estado", params={"servicio_id": base["servicio"].id}
    )

    data = response.json()
    assert data["total"] == 1
    assert data["por_estado"]["pendiente"] == 1


def test_reservaciones_por_estado_filtra_por_origen(client, db_session, base):
    cliente_2 = _crear_cliente_extra(db_session, "Estado Origen 2")
    base_2 = dict(base, cliente=cliente_2)

    _crear_reservacion(db_session, base, estado="pendiente", origen="recepcion")
    _crear_reservacion(db_session, base_2, estado="confirmada", origen="portal")

    response = client.get("/reportes/reservaciones-por-estado", params={"origen": "portal"})

    data = response.json()
    assert data["total"] == 1
    assert data["por_estado"]["confirmada"] == 1


# --- /reportes/cancelaciones -------------------------------------


def test_cancelaciones_calcula_tasa(client, db_session, base):
    cliente_2 = _crear_cliente_extra(db_session, "Cancelacion Cliente 2")
    base_2 = dict(base, cliente=cliente_2)

    _crear_reservacion(db_session, base, estado="cancelada")
    _crear_reservacion(db_session, base_2, estado="pendiente")

    response = client.get("/reportes/cancelaciones")

    data = response.json()
    assert data["total_reservaciones"] == 2
    assert data["num_canceladas"] == 1
    assert data["tasa_cancelacion"] == 50.0


def test_cancelaciones_desglose_por_servicio(client, db_session, base):
    otro_servicio = Servicio(nombre="Otro Cancelacion", precio=Decimal("100.00"))
    db_session.add(otro_servicio)
    db_session.commit()
    db_session.refresh(otro_servicio)

    cliente_2 = _crear_cliente_extra(db_session, "Cancelacion Desglose 2")
    base_2 = dict(base, servicio=otro_servicio, cliente=cliente_2)

    _crear_reservacion(db_session, base, estado="cancelada")
    _crear_reservacion(db_session, base_2, estado="cancelada")

    response = client.get("/reportes/cancelaciones")

    desglose = response.json()["desglose_por_servicio"]
    assert len(desglose) == 2
    assert all(item["num_cancelaciones"] == 1 for item in desglose)


def test_cancelaciones_sin_reservaciones_da_tasa_cero(client):
    response = client.get(
        "/reportes/cancelaciones", params={"desde": "2020-01-01", "hasta": "2020-01-31"}
    )

    data = response.json()
    assert data["total_reservaciones"] == 0
    assert data["tasa_cancelacion"] == 0.0


# --- /reportes/tendencia-reservaciones ---------------------------


def test_tendencia_agrupada_por_dia(client, db_session, base):
    cliente_2 = _crear_cliente_extra(db_session, "Tendencia Cliente 2")
    base_2 = dict(base, cliente=cliente_2)

    _crear_reservacion(
        db_session, base, fecha_creacion=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    )
    _crear_reservacion(
        db_session, base_2, fecha_creacion=datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc)
    )

    response = client.get(
        "/reportes/tendencia-reservaciones", params={"desde": "2026-07-01", "hasta": "2026-07-31"}
    )

    data = response.json()
    assert data["total"] == 2
    assert len(data["serie"]) == 2
    assert data["serie"][0] == {"periodo": "2026-07-01", "num_reservaciones": 1}
    assert data["serie"][1] == {"periodo": "2026-07-02", "num_reservaciones": 1}


def test_tendencia_agrupada_por_mes(client, db_session, base):
    cliente_2 = _crear_cliente_extra(db_session, "Tendencia Mes 2")
    base_2 = dict(base, cliente=cliente_2)

    _crear_reservacion(
        db_session, base, fecha_creacion=datetime(2026, 7, 5, tzinfo=timezone.utc)
    )
    _crear_reservacion(
        db_session, base_2, fecha_creacion=datetime(2026, 7, 20, tzinfo=timezone.utc)
    )

    response = client.get(
        "/reportes/tendencia-reservaciones",
        params={"desde": "2026-07-01", "hasta": "2026-07-31", "agrupar_por": "mes"},
    )

    data = response.json()
    assert len(data["serie"]) == 1
    assert data["serie"][0] == {"periodo": "2026-07", "num_reservaciones": 2}


def test_tendencia_filtra_por_estado(client, db_session, base):
    cliente_2 = _crear_cliente_extra(db_session, "Tendencia Estado 2")
    base_2 = dict(base, cliente=cliente_2)

    _crear_reservacion(
        db_session, base, estado="pendiente",
        fecha_creacion=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    _crear_reservacion(
        db_session, base_2, estado="cancelada",
        fecha_creacion=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )

    response = client.get(
        "/reportes/tendencia-reservaciones",
        params={"desde": "2026-07-01", "hasta": "2026-07-31", "estado": "cancelada"},
    )

    data = response.json()
    assert data["total"] == 1


def test_tendencia_agrupar_por_invalido_da_400(client):
    response = client.get("/reportes/tendencia-reservaciones", params={"agrupar_por": "hora"})
    assert response.status_code == 400


def test_tendencia_estado_invalido_da_400(client):
    response = client.get(
        "/reportes/tendencia-reservaciones", params={"estado": "no-existe"}
    )
    assert response.status_code == 400


def test_tendencia_requiere_admin(client_no_admin):
    response = client_no_admin.get("/reportes/tendencia-reservaciones")
    assert response.status_code == 403


# =====================================================================
# Mini-entrega: huecos para Dashboard (clientes nuevos, próximas
# reservaciones, ingresos agrupados por método de pago)
# =====================================================================

# --- /reportes/clientes-nuevos ---------------------------------------


def test_clientes_nuevos_cuenta_en_rango(client, db_session):
    c1 = Cliente(nombre="Nuevo 1")
    c2 = Cliente(nombre="Nuevo 2")
    db_session.add_all([c1, c2])
    db_session.commit()
    for c in (c1, c2):
        db_session.refresh(c)

    c1.fecha_creacion = datetime(2026, 7, 1, tzinfo=timezone.utc)
    c2.fecha_creacion = datetime(2026, 7, 2, tzinfo=timezone.utc)
    db_session.commit()

    response = client.get(
        "/reportes/clientes-nuevos", params={"desde": "2026-07-01", "hasta": "2026-07-31"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["serie"]) == 2


def test_clientes_nuevos_agrupado_por_mes(client, db_session):
    c1 = Cliente(nombre="Nuevo Mes 1")
    c2 = Cliente(nombre="Nuevo Mes 2")
    db_session.add_all([c1, c2])
    db_session.commit()
    for c in (c1, c2):
        db_session.refresh(c)

    c1.fecha_creacion = datetime(2026, 7, 5, tzinfo=timezone.utc)
    c2.fecha_creacion = datetime(2026, 7, 20, tzinfo=timezone.utc)
    db_session.commit()

    response = client.get(
        "/reportes/clientes-nuevos",
        params={"desde": "2026-07-01", "hasta": "2026-07-31", "agrupar_por": "mes"},
    )

    data = response.json()
    assert data["total"] == 2
    assert data["serie"] == [{"periodo": "2026-07", "num_clientes": 2}]


def test_clientes_nuevos_fuera_de_rango_no_cuenta(client, db_session):
    c1 = Cliente(nombre="Viejo")
    db_session.add(c1)
    db_session.commit()
    db_session.refresh(c1)
    c1.fecha_creacion = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db_session.commit()

    response = client.get(
        "/reportes/clientes-nuevos", params={"desde": "2026-07-01", "hasta": "2026-07-31"}
    )

    assert response.json()["total"] == 0


def test_clientes_nuevos_agrupar_por_metodo_pago_rechazado(client):
    # metodo_pago no es una agrupación válida para clientes (solo para ingresos)
    response = client.get(
        "/reportes/clientes-nuevos", params={"agrupar_por": "metodo_pago"}
    )
    assert response.status_code == 400


def test_clientes_nuevos_requiere_admin(client_no_admin):
    response = client_no_admin.get("/reportes/clientes-nuevos")
    assert response.status_code == 403


# --- /reportes/proximas-reservaciones ---------------------------


def test_proximas_reservaciones_dentro_de_la_ventana(client, db_session, base):
    hoy = datetime.now(timezone.utc).date()
    _crear_reservacion(
        db_session, base, estado="confirmada", fecha_visita=hoy + timedelta(days=3)
    )

    response = client.get("/reportes/proximas-reservaciones")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["cliente_nombre"] == base["cliente"].nombre


def test_proximas_reservaciones_excluye_fuera_de_ventana(client, db_session, base):
    hoy = datetime.now(timezone.utc).date()
    _crear_reservacion(
        db_session, base, estado="confirmada", fecha_visita=hoy + timedelta(days=30)
    )

    response = client.get("/reportes/proximas-reservaciones")

    assert response.json()["total"] == 0


def test_proximas_reservaciones_excluye_pendientes_por_default(client, db_session, base):
    hoy = datetime.now(timezone.utc).date()
    _crear_reservacion(db_session, base, estado="pendiente", fecha_visita=hoy + timedelta(days=2))

    response = client.get("/reportes/proximas-reservaciones")

    assert response.json()["total"] == 0


def test_proximas_reservaciones_permite_filtrar_otro_estado(client, db_session, base):
    hoy = datetime.now(timezone.utc).date()
    _crear_reservacion(db_session, base, estado="pendiente", fecha_visita=hoy + timedelta(days=2))

    response = client.get("/reportes/proximas-reservaciones", params={"estado": "pendiente"})

    assert response.json()["total"] == 1


def test_proximas_reservaciones_respeta_parametro_dias(client, db_session, base):
    hoy = datetime.now(timezone.utc).date()
    _crear_reservacion(
        db_session, base, estado="confirmada", fecha_visita=hoy + timedelta(days=10)
    )

    respuesta_7_dias = client.get("/reportes/proximas-reservaciones")
    respuesta_14_dias = client.get("/reportes/proximas-reservaciones", params={"dias": 14})

    assert respuesta_7_dias.json()["total"] == 0
    assert respuesta_14_dias.json()["total"] == 1


def test_proximas_reservaciones_ordenadas_por_fecha(client, db_session, base):
    hoy = datetime.now(timezone.utc).date()
    cliente_2 = _crear_cliente_extra(db_session, "Proximas Cliente 2")
    base_2 = dict(base, cliente=cliente_2)

    _crear_reservacion(db_session, base_2, estado="confirmada", fecha_visita=hoy + timedelta(days=5))
    _crear_reservacion(db_session, base, estado="confirmada", fecha_visita=hoy + timedelta(days=1))

    response = client.get("/reportes/proximas-reservaciones")

    items = response.json()["items"]
    assert items[0]["fecha_visita"] < items[1]["fecha_visita"]


def test_proximas_reservaciones_dias_invalido_rechazado(client):
    response = client.get("/reportes/proximas-reservaciones", params={"dias": 0})
    assert response.status_code == 400


def test_proximas_reservaciones_estado_invalido_rechazado(client):
    response = client.get(
        "/reportes/proximas-reservaciones", params={"estado": "no-existe"}
    )
    assert response.status_code == 400


def test_proximas_reservaciones_requiere_admin(client_no_admin):
    response = client_no_admin.get("/reportes/proximas-reservaciones")
    assert response.status_code == 403


# --- /reportes/ingresos agrupado por método de pago ---------------


def test_ingresos_agrupado_por_metodo_pago(client, db_session, base):
    r1 = _crear_reservacion(db_session, base)
    _crear_pago(
        db_session, r1, base, Decimal("300.00"), metodo_pago="efectivo",
        fecha_pago=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    _crear_pago(
        db_session, r1, base, Decimal("500.00"), metodo_pago="tarjeta",
        fecha_pago=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )
    _crear_pago(
        db_session, r1, base, Decimal("100.00"), metodo_pago="tarjeta",
        fecha_pago=datetime(2026, 7, 3, tzinfo=timezone.utc),
    )

    response = client.get(
        "/reportes/ingresos",
        params={"desde": "2026-07-01", "hasta": "2026-07-31", "agrupar_por": "metodo_pago"},
    )

    assert response.status_code == 200
    data = response.json()
    serie_por_metodo = {item["periodo"]: item["ingresos"] for item in data["serie"]}
    assert serie_por_metodo["efectivo"] == "300.00"
    assert serie_por_metodo["tarjeta"] == "600.00"
    assert data["total_ingresos"] == "900.00"


def test_ingresos_agrupado_por_metodo_pago_incluye_reembolsos(client, db_session, base):
    r1 = _crear_reservacion(db_session, base)
    _crear_pago(
        db_session, r1, base, Decimal("500.00"), metodo_pago="efectivo", tipo="pago_completo",
        fecha_pago=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    _crear_pago(
        db_session, r1, base, Decimal("50.00"), metodo_pago="efectivo", tipo="reembolso",
        fecha_pago=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )

    response = client.get(
        "/reportes/ingresos",
        params={"desde": "2026-07-01", "hasta": "2026-07-31", "agrupar_por": "metodo_pago"},
    )

    serie = response.json()["serie"]
    assert len(serie) == 1
    assert serie[0]["periodo"] == "efectivo"
    assert serie[0]["ingresos"] == "500.00"
    assert serie[0]["reembolsos"] == "50.00"
    assert serie[0]["neto"] == "450.00"

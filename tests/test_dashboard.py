"""
Pruebas de /dashboard/resumen. Mismo patrón de SQLite en memoria que
los demás módulos. Las fechas de comparación (hoy/ayer, mes actual/mes
anterior) se calculan dinámicamente con datetime.now(), igual que en
test_reportes.py — nunca se hardcodea una fecha fija, para que las
pruebas sigan siendo válidas sin importar cuándo se corran.

Correr con:
    pytest tests/test_dashboard.py -v
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models.caja import CajaMovimiento, CajaSesion  # noqa: F401
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
    rol = Rol(nombre="admin", descripcion="Admin de prueba")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Admin Dashboard",
        email="admin-dashboard@ejixhole.com",
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
    rol = Rol(nombre="operador_dashboard_test", descripcion="Operador")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Operador Dashboard",
        email="operador-dashboard@ejixhole.com",
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
    rol = Rol(nombre="cajero_dashboard_test", descripcion="Cajero")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)

    usuario = Usuario(
        nombre="Cajero Dashboard",
        email="cajero-dashboard@ejixhole.com",
        password_hash="hash-falso",
        rol_id=rol.id,
    )
    cliente = Cliente(nombre="Cliente Dashboard Test")
    servicio = Servicio(nombre="Tour Dashboard", precio=Decimal("500.00"), capacidad_maxima=10)
    db_session.add_all([usuario, cliente, servicio])
    db_session.commit()
    db_session.refresh(usuario)
    db_session.refresh(cliente)
    db_session.refresh(servicio)

    return {"usuario": usuario, "cliente": cliente, "servicio": servicio}


def _crear_cliente_extra(db_session, nombre):
    cliente = Cliente(nombre=nombre)
    db_session.add(cliente)
    db_session.commit()
    db_session.refresh(cliente)
    return cliente


def _crear_reservacion(
    db_session, base, total=Decimal("1000.00"), monto_pagado=Decimal("0"), estado="pendiente",
    fecha_creacion=None, fecha_visita=None, num_personas=2,
):
    reservacion = Reservacion(
        cliente_id=base["cliente"].id,
        servicio_id=base["servicio"].id,
        usuario_id=base["usuario"].id,
        fecha_visita=fecha_visita or datetime.now(timezone.utc).date(),
        num_personas=num_personas,
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


def _crear_pago(db_session, reservacion, base, monto, tipo="pago_completo", fecha_pago=None):
    pago = Pago(
        reservacion_id=reservacion.id,
        usuario_id=base["usuario"].id,
        monto=monto,
        tipo=tipo,
        metodo_pago="efectivo",
    )
    if fecha_pago is not None:
        pago.fecha_pago = fecha_pago
    db_session.add(pago)
    db_session.commit()
    db_session.refresh(pago)
    return pago


def _tarjeta_por_titulo(data, titulo):
    return next(t for t in data["tarjetas"] if t["titulo"] == titulo)


# --- Autenticación / autorización -------------------------------


def test_resumen_sin_token_da_401():
    response = TestClient(app).get("/dashboard/resumen")
    assert response.status_code == 401


def test_resumen_requiere_admin(client_no_admin):
    response = client_no_admin.get("/dashboard/resumen")
    assert response.status_code == 403


# --- Estructura general -------------------------------------------


def test_resumen_devuelve_las_9_tarjetas_esperadas(client):
    response = client.get("/dashboard/resumen")

    assert response.status_code == 200
    data = response.json()
    titulos = {t["titulo"] for t in data["tarjetas"]}
    assert titulos == {
        "Ingresos hoy",
        "Ingresos del mes",
        "Reservaciones activas",
        "Próximas 7 días",
        "Saldo pendiente total",
        "Tasa de cancelación (mes)",
        "Ocupación promedio (mes)",
        "Diferencia de caja (hoy)",
        "Clientes nuevos (mes)",
    }


def test_resumen_sin_datos_no_truena(client):
    """Con la base vacía, todo debe dar valores neutros, no error."""
    response = client.get("/dashboard/resumen")

    assert response.status_code == 200
    data = response.json()
    assert _tarjeta_por_titulo(data, "Reservaciones activas")["valor"] == 0
    assert _tarjeta_por_titulo(data, "Próximas 7 días")["valor"] == 0
    assert _tarjeta_por_titulo(data, "Clientes nuevos (mes)")["valor"] == 0


# --- Tarjetas individuales -----------------------------------------


def test_ingresos_hoy_vs_ayer(client, db_session, base):
    hoy = datetime.now(timezone.utc)
    ayer = hoy - timedelta(days=1)

    r1 = _crear_reservacion(db_session, base, fecha_creacion=hoy)
    _crear_pago(db_session, r1, base, Decimal("300.00"), fecha_pago=hoy)
    _crear_pago(db_session, r1, base, Decimal("100.00"), fecha_pago=ayer)

    response = client.get("/dashboard/resumen")

    data = response.json()
    tarjeta = _tarjeta_por_titulo(data, "Ingresos hoy")
    assert tarjeta["valor"] == "300.00"
    assert tarjeta["comparacion_valor_anterior"] == "100.00"
    assert tarjeta["tendencia"] == "up"
    assert tarjeta["comparacion_porcentaje"] == 200.0


def test_reservaciones_activas_suma_pendiente_y_confirmada(client, db_session, base):
    hoy = datetime.now(timezone.utc)
    cliente_2 = _crear_cliente_extra(db_session, "Dashboard Activas 2")
    cliente_3 = _crear_cliente_extra(db_session, "Dashboard Activas 3")
    base_2 = dict(base, cliente=cliente_2)
    base_3 = dict(base, cliente=cliente_3)

    _crear_reservacion(db_session, base, estado="pendiente", fecha_creacion=hoy)
    _crear_reservacion(db_session, base_2, estado="confirmada", fecha_creacion=hoy)
    _crear_reservacion(db_session, base_3, estado="cancelada", fecha_creacion=hoy)

    response = client.get("/dashboard/resumen")

    tarjeta = _tarjeta_por_titulo(response.json(), "Reservaciones activas")
    assert tarjeta["valor"] == 2


def test_proximas_7_dias_cuenta_confirmadas(client, db_session, base):
    hoy_fecha = datetime.now(timezone.utc).date()
    _crear_reservacion(
        db_session, base, estado="confirmada", fecha_visita=hoy_fecha + timedelta(days=3)
    )

    response = client.get("/dashboard/resumen")

    tarjeta = _tarjeta_por_titulo(response.json(), "Próximas 7 días")
    assert tarjeta["valor"] == 1


def test_saldo_pendiente_total(client, db_session, base):
    _crear_reservacion(db_session, base, total=Decimal("1000.00"), monto_pagado=Decimal("400.00"))

    response = client.get("/dashboard/resumen")

    tarjeta = _tarjeta_por_titulo(response.json(), "Saldo pendiente total")
    assert tarjeta["valor"] == "600.00"


def test_tasa_cancelacion_del_mes(client, db_session, base):
    hoy = datetime.now(timezone.utc)
    cliente_2 = _crear_cliente_extra(db_session, "Dashboard Cancelacion 2")
    base_2 = dict(base, cliente=cliente_2)

    _crear_reservacion(db_session, base, estado="cancelada", fecha_creacion=hoy)
    _crear_reservacion(db_session, base_2, estado="pendiente", fecha_creacion=hoy)

    response = client.get("/dashboard/resumen")

    tarjeta = _tarjeta_por_titulo(response.json(), "Tasa de cancelación (mes)")
    assert tarjeta["valor"] == 50.0


def test_clientes_nuevos_del_mes(client, db_session, base):
    hoy = datetime.now(timezone.utc)
    c1 = _crear_cliente_extra(db_session, "Nuevo Dashboard 1")
    c1.fecha_creacion = hoy
    db_session.commit()

    response = client.get("/dashboard/resumen")

    tarjeta = _tarjeta_por_titulo(response.json(), "Clientes nuevos (mes)")
    # +1 por el cliente de la fixture `base`, que también se crea "ahora"
    assert tarjeta["valor"] >= 1


def test_diferencia_caja_hoy_suma_sesiones_cerradas(client, db_session, base):
    sesion = CajaSesion(
        usuario_id=base["usuario"].id,
        monto_apertura=Decimal("200.00"),
        estado="cerrada",
        monto_cierre_esperado=Decimal("200.00"),
        monto_cierre_real=Decimal("180.00"),
        diferencia=Decimal("-20.00"),
    )
    db_session.add(sesion)
    db_session.commit()

    response = client.get("/dashboard/resumen")

    tarjeta = _tarjeta_por_titulo(response.json(), "Diferencia de caja (hoy)")
    assert tarjeta["valor"] == "-20.00"


def test_ocupacion_promedio_es_cero_sin_reservaciones_con_capacidad(client):
    response = client.get("/dashboard/resumen")

    tarjeta = _tarjeta_por_titulo(response.json(), "Ocupación promedio (mes)")
    assert tarjeta["valor"] == 0


def test_tarjeta_sin_comparacion_no_trae_tendencia(client):
    response = client.get("/dashboard/resumen")

    tarjeta = _tarjeta_por_titulo(response.json(), "Reservaciones activas")
    assert tarjeta["comparacion_valor_anterior"] is None
    assert tarjeta["comparacion_porcentaje"] is None
    assert tarjeta["tendencia"] is None

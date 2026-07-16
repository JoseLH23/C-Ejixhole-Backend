"""
conftest.py — corre ANTES de que pytest importe cualquier módulo de
`app`, así que es el lugar correcto para fijar variables de entorno
que la configuración necesita al arrancar.

CR-01: los tests usan una clave JWT explícita de prueba.
El flujo de efectivo estricto se prueba de forma dedicada en
`tests/test_flujo_visita.py`; las pruebas históricas de Pago conservan su
alcance aislado sin tener que montar una sesión de Caja en cada caso.
"""
import os

import pytest

os.environ.setdefault(
    "JWT_SECRET_KEY", "clave-de-pruebas-nunca-usar-en-produccion-" + "x" * 20
)
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("REQUIRE_OPEN_CASH_FOR_CASH_PAYMENTS", "false")


@pytest.fixture(autouse=True)
def _limpiar_rate_limiters():
    """
    Los rate limiters (app/core/rate_limiter.py) son singletons a
    nivel de módulo — sin esto, las llamadas de un test se acumulan
    sobre las del siguiente dentro de la MISMA corrida de pytest.
    """
    from app.core.rate_limiter import limitador_login, limitador_publico

    limitador_login._llamadas.clear()
    limitador_publico._llamadas.clear()
    yield

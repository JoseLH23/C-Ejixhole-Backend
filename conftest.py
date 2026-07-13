"""
conftest.py — corre ANTES de que pytest importe cualquier módulo de
`app`, así que es el lugar correcto para fijar variables de entorno
que la configuración necesita al arrancar.

CR-01 (auditoría de seguridad): app/core/config.py ya no arranca con
ningún valor por defecto para JWT_SECRET_KEY — así que los tests
necesitan una clave real (aunque sea obviamente de prueba) para poder
importar la app en absoluto.
"""
import os

import pytest

os.environ.setdefault(
    "JWT_SECRET_KEY", "clave-de-pruebas-nunca-usar-en-produccion-" + "x" * 20
)


@pytest.fixture(autouse=True)
def _limpiar_rate_limiters():
    """
    Los rate limiters (app/core/rate_limiter.py) son singletons a
    nivel de módulo — sin esto, las llamadas de un test se acumulan
    sobre las del siguiente dentro de la MISMA corrida de pytest, y
    tests que en producción son legítimos (varios logins en tests
    distintos) empiezan a recibir 429 por error, no por el
    comportamiento real que se está probando.
    """
    from app.core.rate_limiter import limitador_login, limitador_publico

    limitador_login._llamadas.clear()
    limitador_publico._llamadas.clear()
    yield

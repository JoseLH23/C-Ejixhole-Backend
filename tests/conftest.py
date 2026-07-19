import pytest

from app.core.rate_limiter import reiniciar_limitadores


@pytest.fixture(autouse=True)
def aislar_limitadores_globales():
    """Evita que el tráfico simulado de una prueba contamine otra."""
    reiniciar_limitadores()
    yield
    reiniciar_limitadores()

import pytest
from fastapi import HTTPException

from app.core.rate_limiter import (
    AdaptiveRateLimiter,
    RateLimiter,
    exigir_limite,
    huella_contacto,
)


class RelojControlado:
    def __init__(self):
        self.ahora = 0.0

    def __call__(self):
        return self.ahora


def test_ventana_deslizante_libera_la_cuota_al_expirar():
    reloj = RelojControlado()
    limitador = RateLimiter(2, 10, reloj=reloj)

    assert limitador.permitido("ip") is True
    assert limitador.permitido("ip") is True
    assert limitador.permitido("ip") is False
    assert limitador.segundos_para_reintentar("ip") == 10

    reloj.ahora = 10.1
    assert limitador.permitido("ip") is True


def test_reincidencia_aumenta_el_bloqueo_adaptativo():
    reloj = RelojControlado()
    limitador = AdaptiveRateLimiter(
        max_llamadas=2,
        ventana_segundos=10,
        penalizacion_inicial_segundos=5,
        penalizacion_maxima_segundos=20,
        reloj=reloj,
    )

    assert limitador.permitido("contacto") is True
    assert limitador.permitido("contacto") is True
    assert limitador.permitido("contacto") is False
    assert limitador.segundos_para_reintentar("contacto") == 5

    reloj.ahora = 5.1
    assert limitador.permitido("contacto") is False
    assert limitador.segundos_para_reintentar("contacto") == 10

    reloj.ahora = 15.2
    assert limitador.permitido("contacto") is True


def test_respuesta_429_incluye_retry_after():
    reloj = RelojControlado()
    limitador = RateLimiter(1, 10, reloj=reloj)
    assert limitador.permitido("ip") is True

    with pytest.raises(HTTPException) as error:
        exigir_limite(limitador, "ip", "Espera")

    assert error.value.status_code == 429
    assert error.value.headers == {"Retry-After": "10"}


def test_huella_de_contacto_es_estable_y_no_conserva_pii():
    primera = huella_contacto(" VISITANTE@Example.com ", "+52 444-123-4567")
    segunda = huella_contacto("visitante@example.com", "524441234567")

    assert primera == segunda
    assert len(primera) == 64
    assert "visitante" not in primera
    assert "4441234567" not in primera

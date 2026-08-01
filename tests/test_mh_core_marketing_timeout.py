import pytest

from app.services.mh_core_marketing_service import MhCoreMarketingService


@pytest.fixture(autouse=True)
def clean_timeout_env(monkeypatch):
    monkeypatch.delenv("MH_CORE_MARKETING_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("MH_CORE_TIMEOUT_SECONDS", raising=False)


def test_marketing_usa_75_segundos_por_defecto():
    assert MhCoreMarketingService().timeout_seconds == 75.0


def test_marketing_prefiere_timeout_dedicado(monkeypatch):
    monkeypatch.setenv("MH_CORE_TIMEOUT_SECONDS", "20")
    monkeypatch.setenv("MH_CORE_MARKETING_TIMEOUT_SECONDS", "90")

    assert MhCoreMarketingService().timeout_seconds == 90.0


def test_marketing_conserva_fallback_general(monkeypatch):
    monkeypatch.setenv("MH_CORE_TIMEOUT_SECONDS", "35")

    assert MhCoreMarketingService().timeout_seconds == 35.0


@pytest.mark.parametrize("value", ["0", "121", "invalido"])
def test_marketing_rechaza_timeout_inseguro(monkeypatch, value):
    monkeypatch.setenv("MH_CORE_MARKETING_TIMEOUT_SECONDS", value)

    with pytest.raises(RuntimeError):
        MhCoreMarketingService()

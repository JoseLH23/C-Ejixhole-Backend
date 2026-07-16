import json

import pytest

from scripts.check_production_health import (
    CheckResult,
    _markdown,
    _validate_backend,
    _validate_react_app,
)


def test_monitor_acepta_backend_listo():
    body = json.dumps(
        {
            "status": "ready",
            "checks": {"database": "up", "notifications": "configured"},
        }
    ).encode()

    assert "PostgreSQL" in _validate_backend(body)


def test_monitor_rechaza_backend_sin_notificaciones():
    body = json.dumps(
        {
            "status": "ready",
            "checks": {"database": "up", "notifications": "not_configured"},
        }
    ).encode()

    with pytest.raises(ValueError, match="notificaciones"):
        _validate_backend(body)


def test_monitor_reconoce_shell_react():
    assert _validate_react_app(b'<html><div id="root"></div></html>')


def test_reporte_no_expone_detalles_adicionales():
    report = _markdown(
        [
            CheckResult(
                name="Backend",
                url="https://example.test/health/ready",
                ok=True,
                latency_ms=25,
                detail="disponible",
            )
        ]
    )

    assert "✅" in report
    assert "25 ms" in report
    assert "example.test" not in report

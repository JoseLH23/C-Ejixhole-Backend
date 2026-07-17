"""Pruebas del arranque de Render con migraciones obligatorias."""
import os
import subprocess
import sys

import pytest

from scripts import start_render


def test_uvicorn_command_usa_port_configurado():
    command = start_render.uvicorn_command("12345")

    assert command == [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "12345",
    ]


@pytest.mark.parametrize("port", ["", "abc", "0", "65536", "-1"])
def test_uvicorn_command_rechaza_port_invalido(port):
    with pytest.raises(RuntimeError, match="PORT"):
        start_render.uvicorn_command(port)


def test_run_migrations_exige_upgrade_head(monkeypatch):
    calls = []

    def fake_run(command, check):
        calls.append((command, check))

    monkeypatch.setattr(subprocess, "run", fake_run)

    start_render.run_migrations()

    assert calls == [([sys.executable, "-m", "alembic", "upgrade", "head"], True)]


def test_main_no_inicia_uvicorn_si_falla_migracion(monkeypatch):
    executed = False

    def fail_migration():
        raise subprocess.CalledProcessError(1, ["alembic"])

    def fake_exec(*_args):
        nonlocal executed
        executed = True

    monkeypatch.setattr(start_render, "run_migrations", fail_migration)
    monkeypatch.setattr(os, "execvpe", fake_exec)

    with pytest.raises(subprocess.CalledProcessError):
        start_render.main()

    assert executed is False


def test_main_migra_antes_de_reemplazar_proceso(monkeypatch):
    order = []

    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setattr(start_render, "run_migrations", lambda: order.append("migrations"))

    def fake_exec(executable, command, environment):
        order.append("uvicorn")
        assert executable == sys.executable
        assert command[-1] == "9000"
        assert environment["PORT"] == "9000"

    monkeypatch.setattr(os, "execvpe", fake_exec)

    start_render.main()

    assert order == ["migrations", "uvicorn"]

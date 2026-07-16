from uuid import UUID

import pytest

from scripts import verify_event_channel
from scripts.verify_event_channel import VerificationError, verify_event


EVENT_ID = UUID("11111111-1111-4111-8111-111111111111")


def test_verifica_publicado_y_registro_unico(monkeypatch):
    responses = iter(
        [
            {"event_id": str(EVENT_ID), "status": "processing"},
            {"event_id": str(EVENT_ID), "status": "published"},
            {"event_id": str(EVENT_ID), "unique_record": True},
        ]
    )
    monkeypatch.setattr(verify_event_channel, "_request_json", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(verify_event_channel.time, "sleep", lambda _seconds: None)

    backend, mh_core = verify_event(
        EVENT_ID,
        backend_url="https://backend.test",
        backend_token="token",
        mh_core_url="https://mh-core.test",
        mh_core_api_key="key",
        wait_seconds=10,
        poll_seconds=1,
    )

    assert backend["status"] == "published"
    assert mh_core["unique_record"] is True


def test_dead_letter_falla_sin_consultar_mh_core(monkeypatch):
    monkeypatch.setattr(
        verify_event_channel,
        "_request_json",
        lambda *_args, **_kwargs: {"event_id": str(EVENT_ID), "status": "dead_letter"},
    )

    with pytest.raises(VerificationError, match="dead_letter"):
        verify_event(
            EVENT_ID,
            backend_url="https://backend.test",
            backend_token="token",
            mh_core_url="https://mh-core.test",
            mh_core_api_key="key",
        )


def test_rechaza_confirmacion_de_otro_evento(monkeypatch):
    responses = iter(
        [
            {"event_id": str(EVENT_ID), "status": "published"},
            {"event_id": "22222222-2222-4222-8222-222222222222", "unique_record": True},
        ]
    )
    monkeypatch.setattr(verify_event_channel, "_request_json", lambda *_args, **_kwargs: next(responses))

    with pytest.raises(VerificationError, match="distinto"):
        verify_event(
            EVENT_ID,
            backend_url="https://backend.test",
            backend_token="token",
            mh_core_url="https://mh-core.test",
            mh_core_api_key="key",
        )

"""Verifica sin escribir datos que un evento llegó una sola vez a MH-Core."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID


class VerificationError(RuntimeError):
    pass


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise VerificationError(f"Falta la variable {name}.")
    return value


def _request_json(url: str, headers: dict[str, str], timeout: int = 30) -> dict:
    request = Request(
        url,
        headers={"Accept": "application/json", "Cache-Control": "no-cache", **headers},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(1_000_000)
    except HTTPError as exc:
        raise VerificationError(f"{url} devolvió HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise VerificationError(f"{url} no respondió.") from exc
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"{url} no devolvió JSON válido.") from exc
    if not isinstance(payload, dict):
        raise VerificationError(f"{url} no devolvió un objeto JSON.")
    return payload


def verify_event(
    event_id: UUID,
    *,
    backend_url: str,
    backend_token: str,
    mh_core_url: str,
    mh_core_api_key: str,
    wait_seconds: int = 120,
    poll_seconds: int = 5,
) -> tuple[dict, dict]:
    backend_event_url = (
        f"{backend_url.rstrip('/')}/api/v1/integrations/mh-core/outbox/events/{event_id}"
    )
    mh_event_url = f"{mh_core_url.rstrip('/')}/integrations/ejixhole/events/{event_id}"
    deadline = time.monotonic() + wait_seconds
    last_backend: dict | None = None

    while True:
        last_backend = _request_json(
            backend_event_url,
            {"Authorization": f"Bearer {backend_token}"},
        )
        if last_backend.get("status") == "published":
            break
        if last_backend.get("status") == "dead_letter":
            raise VerificationError("El evento terminó en dead_letter.")
        if time.monotonic() >= deadline:
            raise VerificationError(
                f"El evento no llegó a published; estado final: {last_backend.get('status')}."
            )
        time.sleep(poll_seconds)

    mh_event = _request_json(mh_event_url, {"X-API-Key": mh_core_api_key})
    if str(mh_event.get("event_id")) != str(event_id):
        raise VerificationError("MH-Core confirmó un identificador distinto.")
    if mh_event.get("unique_record") is not True:
        raise VerificationError("MH-Core no confirmó un registro único.")
    return last_backend, mh_event


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Confirma la entrega única de un evento EjiXhole -> MH-Core."
    )
    parser.add_argument("event_id", type=UUID)
    args = parser.parse_args()

    try:
        backend, mh_core = verify_event(
            args.event_id,
            backend_url=os.getenv(
                "BACKEND_URL", "https://c-ejixhole-backend.onrender.com"
            ),
            backend_token=_required("BACKEND_ADMIN_TOKEN"),
            mh_core_url=_required("MH_CORE_URL"),
            mh_core_api_key=_required("MH_CORE_API_KEY"),
            wait_seconds=int(os.getenv("EVENT_VERIFY_WAIT_SECONDS", "120")),
            poll_seconds=int(os.getenv("EVENT_VERIFY_POLL_SECONDS", "5")),
        )
    except (VerificationError, ValueError) as exc:
        print(f"CANAL NO VERIFICADO: {exc}", file=sys.stderr)
        return 1

    print(
        "CANAL VERIFICADO: "
        f"event_id={args.event_id} backend={backend['status']} "
        f"mh_core_unique={mh_core['unique_record']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

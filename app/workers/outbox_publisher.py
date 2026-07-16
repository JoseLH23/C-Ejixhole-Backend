"""Ejecuta el publicador de eventos como proceso independiente.

Uso continuo:
    python -m app.workers.outbox_publisher

Una sola pasada, útil para cron o diagnóstico:
    python -m app.workers.outbox_publisher --once
"""
from __future__ import annotations

import argparse
import logging

from app.services.outbox_publisher_service import (
    OutboxPublisher,
    OutboxPublisherConfigurationError,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publica el outbox de EjiXhole hacia MH-Core.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Procesa un lote disponible y termina.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    try:
        publisher = OutboxPublisher()
    except OutboxPublisherConfigurationError as exc:
        logging.getLogger("ejixhole.outbox").error("Configuración inválida: %s", exc)
        return 2

    if args.once:
        stats = publisher.publish_once()
        logging.getLogger("ejixhole.outbox").info("Resultado de una pasada: %s", stats)
        return 0

    publisher.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.proteccion_publica_config import LIMITE_CLIENTE_HORA, LIMITE_CONTACTO_DIA, LIMITE_IP_HORA
from app.models.intento_publico import IntentoPublico


@dataclass(frozen=True)
class DecisionIntento:
    intento: IntentoPublico
    motivo: str | None
    reintentar_en: int | None
    permitido: bool


class IntentoPublicoRepository:
    def __init__(self, db: Session):
        self.db = db

    def _bloquear(self, *values: str | None) -> None:
        if self.db.get_bind().dialect.name != "postgresql":
            return
        for value in sorted({item for item in values if item}):
            number = int(value[:16], 16)
            if number >= 2**63:
                number -= 2**64
            self.db.execute(text("SELECT pg_advisory_xact_lock(:value)"), {"value": number})

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    def _cuota(self, field, value, now, window, limit) -> tuple[bool, int | None]:
        if value is None:
            return False, None
        rows = (
            self.db.query(IntentoPublico)
            .filter(
                field == value,
                IntentoPublico.created_at >= now - window,
                IntentoPublico.allowed.is_(True),
            )
            .order_by(IntentoPublico.created_at.asc())
            .all()
        )
        if len(rows) < limit:
            return False, None
        oldest = self._aware(rows[0].created_at)
        seconds = max(1, math.ceil((oldest + window - now).total_seconds()))
        return True, seconds

    def reservar(
        self,
        *,
        ip_hash: str,
        contact_hash: str | None,
        client_hash: str | None,
        nonce_hash: str | None,
        motivo_inicial: str | None,
        reintentar_inicial: int | None,
        modo: str,
        ahora: datetime,
    ) -> DecisionIntento:
        self._bloquear(ip_hash, contact_hash, client_hash, nonce_hash)
        motivo = motivo_inicial
        reintentar_en = reintentar_inicial

        if motivo is None and nonce_hash and self.db.query(IntentoPublico).filter(
            IntentoPublico.nonce_hash == nonce_hash
        ).first():
            motivo = "challenge_reused"

        checks = (
            (IntentoPublico.ip_hash, ip_hash, timedelta(hours=1), LIMITE_IP_HORA, "ip_limit"),
            (IntentoPublico.contact_hash, contact_hash, timedelta(days=1), LIMITE_CONTACTO_DIA, "contact_limit"),
            (IntentoPublico.client_hash, client_hash, timedelta(hours=1), LIMITE_CLIENTE_HORA, "client_limit"),
        )
        for field, value, window, limit, label in checks:
            if motivo is not None:
                break
            exceeded, seconds = self._cuota(field, value, ahora, window, limit)
            if exceeded:
                motivo, reintentar_en = label, seconds

        permitido = motivo is None or modo == "monitor"
        stored_nonce = None if motivo == "challenge_reused" else nonce_hash
        intento = IntentoPublico(
            ip_hash=ip_hash,
            contact_hash=contact_hash,
            client_hash=client_hash,
            nonce_hash=stored_nonce,
            allowed=permitido,
            mode=modo,
            reason=motivo or "ok",
        )
        self.db.add(intento)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            motivo = "challenge_reused"
            permitido = modo == "monitor"
            intento = IntentoPublico(
                ip_hash=ip_hash,
                contact_hash=contact_hash,
                client_hash=client_hash,
                nonce_hash=None,
                allowed=permitido,
                mode=modo,
                reason=motivo,
            )
            self.db.add(intento)
            self.db.commit()
        return DecisionIntento(intento, motivo, reintentar_en, permitido)

    def liberar(self, intento: IntentoPublico) -> None:
        if not intento.allowed:
            return
        self.db.query(IntentoPublico).filter(IntentoPublico.id == intento.id).delete()
        self.db.commit()

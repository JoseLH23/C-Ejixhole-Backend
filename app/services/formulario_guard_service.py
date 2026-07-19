import hashlib
import hmac
from datetime import datetime, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.desafio_formulario import DesafioFormulario
from app.core.proteccion_publica_config import MODO_PROTECCION_PUBLICA
from app.models.intento_publico import IntentoPublico
from app.repositories.intento_publico_repository import IntentoPublicoRepository
from app.services.audit_service import AuditService


class FormularioGuardService:
    def __init__(self, db: Session):
        self.db = db
        self.desafio = DesafioFormulario()
        self.intentos = IntentoPublicoRepository(db)

    @staticmethod
    def _ip(request: Request) -> str:
        values = [item.strip() for item in request.headers.get("x-forwarded-for", "").split(",") if item.strip()]
        if values:
            return values[-1]
        return request.client.host if request.client else "unknown"

    @staticmethod
    def _seudonimo(namespace: str, value: str | None) -> str | None:
        if not value:
            return None
        return hmac.new(
            settings.JWT_SECRET_KEY.encode("utf-8"),
            f"{namespace}:{value}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def crear_desafio(self) -> dict:
        return self.desafio.crear(MODO_PROTECCION_PUBLICA)

    def reservar(self, request: Request, data) -> IntentoPublico:
        email = str(getattr(data, "email", "")).strip().lower()
        phone = "".join(char for char in str(getattr(data, "telefono", "")) if char.isdigit())
        client_value = request.headers.get("x-public-client", "").strip()[:120]
        check = self.desafio.validar(getattr(data, "form_challenge", None))
        motivo = check.motivo
        if str(getattr(data, "website", "") or "").strip():
            motivo = "honeypot_filled"

        decision = self.intentos.reservar(
            ip_hash=self._seudonimo("ip", self._ip(request)),
            contact_hash=self._seudonimo("contact", f"{email}|{phone}"),
            client_hash=self._seudonimo("client", client_value),
            nonce_hash=self._seudonimo("nonce", check.nonce),
            motivo_inicial=motivo,
            reintentar_inicial=check.reintentar_en,
            modo=MODO_PROTECCION_PUBLICA,
            ahora=datetime.now(timezone.utc),
        )

        if decision.motivo:
            AuditService(self.db).registrar(
                actor=None,
                accion="publico.antiabuso_detectado",
                entidad_tipo="public_submission",
                entidad_id=decision.intento.id,
                request=request,
                contexto={"reason": decision.motivo, "mode": MODO_PROTECCION_PUBLICA},
                origen="portal_publico",
            )

        if not decision.permitido:
            if decision.reintentar_en is not None:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="No fue posible procesar la solicitud en este momento.",
                    headers={"Retry-After": str(decision.reintentar_en)},
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fue posible validar el formulario.",
            )
        return decision.intento

    def liberar(self, intento: IntentoPublico) -> None:
        self.intentos.liberar(intento)

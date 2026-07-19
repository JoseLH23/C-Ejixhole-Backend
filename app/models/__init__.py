"""Importa modelos para registrar metadata SQLAlchemy."""
from app.models.usuario import Rol, Usuario  # noqa: F401
from app.models.auth_session import AuthSession  # noqa: F401
from app.models.cliente import Cliente  # noqa: F401
from app.models.servicio import Servicio  # noqa: F401
from app.models.reservacion import Reservacion  # noqa: F401
from app.models.unidad_hospedaje import UnidadHospedaje  # noqa: F401
from app.models.pago import Pago  # noqa: F401
from app.models.caja import CajaSesion, CajaMovimiento  # noqa: F401
from app.models.configuracion import Configuracion, Respaldo  # noqa: F401
from app.models.idempotency_key import IdempotencyKey  # noqa: F401
from app.models.evento_calendario import EventoCalendario  # noqa: F401
from app.models.tarifa_especial import TarifaEspecial  # noqa: F401
from app.models.outbox_event import OutboxEvent  # noqa: F401
from app.models.audit_event import AuditEvent  # noqa: F401
from app.models.public_submission_attempt import PublicSubmissionAttempt  # noqa: F401

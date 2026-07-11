"""
Notificación por correo de reservaciones nuevas del portal público.

Diseño deliberado: si SMTP no está configurado (SMTP_HOST vacío), NO
se lanza ningún error — solo se registra en el log que el correo no
se envió. La reservación ya se creó y ya es visible en el Dashboard;
el correo es un extra, nunca debe poder tumbar la creación real.
"""
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.models.reservacion import Reservacion

logger = logging.getLogger("ejixhole.notificaciones")


def _smtp_configurado() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.NOTIFICACIONES_EMAIL_DESTINO)


def notificar_nueva_reservacion_publica(reservacion: Reservacion) -> None:
    asunto = f"Nueva solicitud de reservación #{reservacion.id} ({reservacion.tipo_reservacion})"
    cuerpo = (
        f"Cliente: {reservacion.cliente.nombre} {reservacion.cliente.apellido or ''}\n"
        f"Teléfono: {reservacion.cliente.telefono or '(no proporcionado)'}\n"
        f"Email: {reservacion.cliente.email or '(no proporcionado)'}\n"
        f"Tipo: {reservacion.tipo_reservacion}\n"
        f"Llegada: {reservacion.fecha_llegada}\n"
        f"Salida: {reservacion.fecha_salida}\n"
        f"Personas: {reservacion.num_personas}\n"
        f"Total: ${reservacion.total}\n"
        f"Estado: {reservacion.estado} (requiere tu confirmación manual)\n"
    )

    if not _smtp_configurado():
        logger.warning(
            "SMTP no configurado — no se envió el correo de la reservación #%s. "
            "La reservación ya está creada y visible en el sistema. "
            "Configura SMTP_HOST/SMTP_USER/SMTP_PASSWORD/NOTIFICACIONES_EMAIL_DESTINO en .env para activarlo.",
            reservacion.id,
        )
        return

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = settings.SMTP_USER
    mensaje["To"] = settings.NOTIFICACIONES_EMAIL_DESTINO
    mensaje.set_content(cuerpo)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as servidor:
            servidor.starttls()
            servidor.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            servidor.send_message(mensaje)
    except Exception:
        # Nunca dejamos que un problema de correo (credenciales
        # incorrectas, servidor caído, etc.) haga fallar la creación
        # de la reservación — ya se guardó correctamente en la BD.
        logger.exception(
            "Falló el envío del correo de la reservación #%s (la reservación sigue creada correctamente).",
            reservacion.id,
        )

"""
Notificación por correo de reservaciones nuevas usando Resend.

Si Resend no está configurado o el envío falla, la reservación
permanece creada correctamente. El correo nunca debe bloquear
el flujo principal.
"""

import logging

import resend

from app.core.config import settings
from app.models.reservacion import Reservacion

logger = logging.getLogger("ejixhole.notificaciones")


def _resend_configurado() -> bool:
    return bool(
        settings.RESEND_API_KEY
        and settings.RESEND_FROM_EMAIL
        and settings.NOTIFICACIONES_EMAIL_DESTINO
    )


def notificar_nueva_reservacion_publica(
    reservacion: Reservacion,
) -> None:
    asunto = (
        f"Nueva solicitud de reservación "
        f"#{reservacion.id} ({reservacion.tipo_reservacion})"
    )

    cuerpo = (
        f"Cliente: {reservacion.cliente.nombre} "
        f"{reservacion.cliente.apellido or ''}\n"
        f"Teléfono: "
        f"{reservacion.cliente.telefono or '(no proporcionado)'}\n"
        f"Email: "
        f"{reservacion.cliente.email or '(no proporcionado)'}\n"
        f"Tipo: {reservacion.tipo_reservacion}\n"
        f"Llegada: {reservacion.fecha_llegada}\n"
        f"Salida: {reservacion.fecha_salida}\n"
        f"Personas: {reservacion.num_personas}\n"
        f"Total: ${reservacion.total}\n"
        f"Estado: {reservacion.estado} "
        f"(requiere tu confirmación manual)\n"
    )

    if not _resend_configurado():
        logger.warning(
            "Resend no configurado — no se envió el correo de la "
            "reservación #%s. La reservación sigue creada.",
            reservacion.id,
        )
        return

    try:
        resend.api_key = settings.RESEND_API_KEY

        respuesta = resend.Emails.send(
            {
                "from": settings.RESEND_FROM_EMAIL,
                "to": [settings.NOTIFICACIONES_EMAIL_DESTINO],
                "subject": asunto,
                "text": cuerpo,
            }
        )

        logger.info(
            "Correo enviado con Resend para la reservación #%s. "
            "Respuesta: %s",
            reservacion.id,
            respuesta,
        )

    except Exception:
        logger.exception(
            "Falló el envío por Resend de la reservación #%s. "
            "La reservación sigue creada correctamente.",
            reservacion.id,
        )
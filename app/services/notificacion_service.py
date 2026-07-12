"""
Notificación por correo de reservaciones nuevas usando Resend.

Si Resend no está configurado o el envío falla, la reservación
permanece creada correctamente. El correo nunca debe bloquear
el flujo principal.

La plantilla HTML usa únicamente tablas y CSS inline (sin <style>,
sin JavaScript, sin imágenes locales) porque es el único enfoque
que Gmail, Outlook y la mayoría de clientes de correo renderizan
de forma consistente. El logo se referencia por URL pública (ya
publicado en el sitio de reservaciones en Vercel), no como archivo
adjunto ni ruta local.
"""

import html
import logging

import resend

from app.core.config import settings
from app.models.reservacion import Reservacion

logger = logging.getLogger("ejixhole.notificaciones")

# Logo público ya usado en producción por ejixhole-reservas
# (ver src/components/layout/Header.tsx y Footer.tsx del repo
# ejixhole-reservas). Se reutiliza tal cual para no depender de
# StaticFiles ni de ningún archivo dentro de este backend.
LOGO_URL = "https://ejixhole-reservas.vercel.app/logo.png?v=3"

# Paleta tomada del logo real (tonos de cascada/agua).
_COLOR_HEADER_BG = "#0e7490"
_COLOR_ACCENT = "#0891b2"
_COLOR_TEXTO = "#1f2937"
_COLOR_TEXTO_SUAVE = "#6b7280"
_COLOR_BORDE = "#e5e7eb"
_COLOR_ESTADO_BG = "#fef3c7"
_COLOR_ESTADO_TEXTO = "#92400e"


def _resend_configurado() -> bool:
    return bool(
        settings.RESEND_API_KEY
        and settings.RESEND_FROM_EMAIL
        and settings.NOTIFICACIONES_EMAIL_DESTINO
    )


def _fila_dato(etiqueta: str, valor: str) -> str:
    """Una fila de la tabla de datos de la reservación (etiqueta + valor)."""
    return f"""
        <tr>
          <td style="padding:10px 0;border-bottom:1px solid {_COLOR_BORDE};
                     font-family:Arial,Helvetica,sans-serif;font-size:13px;
                     color:{_COLOR_TEXTO_SUAVE};width:140px;
                     vertical-align:top;">
            {html.escape(etiqueta)}
          </td>
          <td style="padding:10px 0;border-bottom:1px solid {_COLOR_BORDE};
                     font-family:Arial,Helvetica,sans-serif;font-size:14px;
                     color:{_COLOR_TEXTO};font-weight:bold;
                     vertical-align:top;">
            {valor}
          </td>
        </tr>"""


def _construir_html(reservacion: Reservacion) -> str:
    """Arma el cuerpo HTML del correo. Solo tablas + CSS inline (Gmail-safe)."""

    folio = f"#{reservacion.id}"
    nombre_completo = html.escape(
        f"{reservacion.cliente.nombre} {reservacion.cliente.apellido or ''}".strip()
    )
    telefono = html.escape(reservacion.cliente.telefono or "(no proporcionado)")
    email_cliente = html.escape(reservacion.cliente.email or "(no proporcionado)")
    tipo = html.escape(reservacion.tipo_reservacion)
    llegada = html.escape(str(reservacion.fecha_llegada or reservacion.fecha_visita))
    salida = html.escape(str(reservacion.fecha_salida)) if reservacion.fecha_salida else None
    personas = html.escape(str(reservacion.num_personas))
    total = html.escape(f"${reservacion.total}")
    estado = html.escape(reservacion.estado)

    filas = [
        _fila_dato("Folio", folio),
        _fila_dato("Cliente", nombre_completo),
        _fila_dato("Teléfono", telefono),
        _fila_dato("Email", email_cliente),
        _fila_dato("Tipo", tipo),
        _fila_dato("Llegada", llegada),
    ]
    if salida:
        filas.append(_fila_dato("Salida", salida))
    filas.append(_fila_dato("Personas", personas))
    filas.append(_fila_dato("Total", total))

    filas_html = "".join(filas)

    return f"""<!DOCTYPE html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Nueva solicitud de reservación</title>
  </head>
  <body style="margin:0;padding:0;background-color:#f3f4f6;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background-color:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="600" cellpadding="0" cellspacing="0"
                 style="max-width:600px;width:100%;background-color:#ffffff;
                        border-radius:8px;overflow:hidden;">

            <!-- Encabezado con logo -->
            <tr>
              <td align="center"
                  style="background-color:{_COLOR_HEADER_BG};padding:24px 20px;">
                <img src="{LOGO_URL}" alt="EjiXhole" width="64" height="64"
                     style="display:block;border-radius:50%;
                            border:2px solid #ffffff;" />
                <div style="font-family:Arial,Helvetica,sans-serif;
                            color:#ffffff;font-size:20px;font-weight:bold;
                            margin-top:12px;">
                  Nueva solicitud de reservación
                </div>
              </td>
            </tr>

            <!-- Cuerpo -->
            <tr>
              <td style="padding:24px 24px 8px 24px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                  {filas_html}
                </table>
              </td>
            </tr>

            <!-- Estado -->
            <tr>
              <td style="padding:16px 24px 24px 24px;">
                <table role="presentation" cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="background-color:{_COLOR_ESTADO_BG};
                               color:{_COLOR_ESTADO_TEXTO};
                               font-family:Arial,Helvetica,sans-serif;
                               font-size:13px;font-weight:bold;
                               padding:8px 14px;border-radius:20px;">
                      Estado: {estado.upper()} — requiere tu confirmación manual
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <!-- Pie -->
            <tr>
              <td style="padding:16px 24px 24px 24px;border-top:1px solid {_COLOR_BORDE};">
                <p style="margin:0;font-family:Arial,Helvetica,sans-serif;
                          font-size:12px;color:{_COLOR_TEXTO_SUAVE};">
                  EjiXhole Experience OS — notificación automática. Confirma o
                  rechaza esta reservación desde el panel interno.
                </p>
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


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

        html_cuerpo = _construir_html(reservacion)

        respuesta = resend.Emails.send(
            {
                "from": settings.RESEND_FROM_EMAIL,
                "to": [settings.NOTIFICACIONES_EMAIL_DESTINO],
                "subject": asunto,
                "text": cuerpo,
                "html": html_cuerpo,
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

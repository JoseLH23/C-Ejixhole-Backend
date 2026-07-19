# Protección del portal público

## Controles implementados

- honeypot invisible y fuera del flujo accesible;
- desafío firmado con expiración y tiempo mínimo;
- límites separados para consultas, desafíos y envíos;
- límites durables por IP, contacto e identificador efímero de pestaña;
- seudonimización HMAC: no se guardan IP, correo ni teléfono en la tabla antiabuso;
- `Retry-After` en bloqueos temporales;
- auditoría de detecciones sin datos personales;
- compatibilidad con `Idempotency-Key` para reintentos seguros.

## Despliegue gradual

`PUBLIC_ANTI_ABUSE_MODE=monitor` es el valor inicial. Detecta y registra señales, pero no interrumpe solicitudes antiguas mientras se despliega el portal actualizado.

Después de revisar la telemetría, cambiar a:

`PUBLIC_ANTI_ABUSE_MODE=enforce`

No requiere un proveedor externo ni CAPTCHA.

## Variables opcionales

- `PUBLIC_CHALLENGE_MIN_SECONDS` — 3 por defecto.
- `PUBLIC_CHALLENGE_TTL_SECONDS` — 7200 por defecto.
- `PUBLIC_IP_HOURLY_LIMIT` — 10 por defecto.
- `PUBLIC_CONTACT_DAILY_LIMIT` — 5 por defecto.
- `PUBLIC_CLIENT_HOURLY_LIMIT` — 8 por defecto.

Las huellas se derivan con una clave existente del servidor y nunca se devuelven al navegador.

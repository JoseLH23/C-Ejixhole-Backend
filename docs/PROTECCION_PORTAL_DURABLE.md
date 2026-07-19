# Protección durable del portal público

El backend conserva los límites adaptativos en memoria como primera línea y añade una segunda capa compartida en PostgreSQL.

## Controles

- desafío firmado con expiración, espera mínima y nonce de un solo uso;
- honeypot excluido del hash de idempotencia;
- cuotas durables por IP, contacto e identificador efímero;
- bloqueos transaccionales para solicitudes concurrentes;
- huellas HMAC sin almacenar IP, correo ni teléfono;
- `Retry-After` calculado con la ventana real;
- auditoría empresarial sin datos personales;
- liberación del intento cuando falla disponibilidad o una regla de negocio.

## Despliegue gradual

1. Desplegar el backend con `PUBLIC_ANTI_ABUSE_MODE=monitor`.
2. Desplegar el portal con soporte de desafío.
3. Revisar las detecciones de auditoría.
4. Cambiar a `PUBLIC_ANTI_ABUSE_MODE=enforce`.

Variables opcionales: `PUBLIC_CHALLENGE_MIN_SECONDS`, `PUBLIC_CHALLENGE_TTL_SECONDS`, `PUBLIC_IP_HOURLY_LIMIT`, `PUBLIC_CONTACT_DAILY_LIMIT` y `PUBLIC_CLIENT_HOURLY_LIMIT`.

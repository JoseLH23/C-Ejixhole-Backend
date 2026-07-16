# Publicar el outbox sin Background Worker pagado

Esta alternativa ejecuta un lote del outbox cada 30 minutos mediante GitHub Actions. Conserva la firma HMAC, los bloqueos, reintentos, `dead_letter` e idempotencia existentes.

## Render: backend EjiXhole

Configura:

```text
MH_CORE_EVENTS_URL=https://mh-core.onrender.com/integrations/ejixhole/events
MH_CORE_EVENT_SIGNING_SECRET=<secreto compartido de 48+ caracteres>
OUTBOX_DISPATCH_KEY=<otra clave aleatoria de 32+ caracteres>
```

`MH_CORE_EVENT_SIGNING_SECRET` debe coincidir con `EJIXHOLE_EVENT_SIGNING_SECRET` en MH-Core. `OUTBOX_DISPATCH_KEY` es exclusiva del disparador y no se reutiliza.

## Render: MH-Core

Configura:

```text
EJIXHOLE_EVENT_SIGNING_SECRET=<mismo secreto de firma>
EJIXHOLE_EVENT_MAX_AGE_SECONDS=300
```

En el plan gratuito la bandeja SQLite sigue siendo efímera. Esta solución activa el transporte sin costo, pero no convierte el almacenamiento local en persistente.

## GitHub Actions

En los secretos del repositorio `C-Ejixhole-Backend` agrega:

```text
EJIXHOLE_BACKEND_URL=https://c-ejixhole-backend.onrender.com
OUTBOX_DISPATCH_KEY=<la misma clave configurada en el backend>
```

El workflow `Publicar outbox sin worker pagado` puede ejecutarse manualmente y también corre a los minutos 07 y 37 de cada hora. Si faltan secretos, termina correctamente sin enviar nada.

## Seguridad

La ruta es únicamente:

```text
POST /api/v1/integrations/mh-core/outbox/publish
X-Outbox-Dispatch-Key: <clave>
```

No acepta JWT administrativo ni la API key de MH-Core. Procesa un solo lote y devuelve únicamente conteos, nunca payloads ni datos personales.

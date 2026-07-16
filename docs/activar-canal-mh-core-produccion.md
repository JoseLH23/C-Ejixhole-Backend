# Activar y verificar EjiXhole → MH-Core en producción

## Configuración del backend web

Aplica `alembic upgrade head`. El backend web genera eventos en la misma base PostgreSQL que usa el worker.

## Proceso worker independiente

Crea un proceso persistente desde este repositorio con el comando:

```text
python -m app.workers.outbox_publisher
```

Debe compartir `DATABASE_URL` con el backend web y configurar:

```text
MH_CORE_EVENTS_URL=https://<host-mh-core>/integrations/ejixhole/events
MH_CORE_EVENT_SIGNING_SECRET=<secreto de 48+ caracteres>
OUTBOX_BATCH_SIZE=10
OUTBOX_MAX_ATTEMPTS=8
OUTBOX_LEASE_SECONDS=120
OUTBOX_INITIAL_BACKOFF_SECONDS=10
OUTBOX_MAX_BACKOFF_SECONDS=3600
OUTBOX_REQUEST_TIMEOUT_SECONDS=10
OUTBOX_POLL_INTERVAL_SECONDS=10
```

El secreto debe coincidir con `EJIXHOLE_EVENT_SIGNING_SECRET` en MH-Core. No reutilices `JWT_SECRET_KEY`, `MH_CORE_SERVICE_KEY` ni `MH_CORE_API_KEY`.

## Diagnóstico administrativo

Con una sesión de administrador:

```text
GET /api/v1/integrations/mh-core/outbox/status
GET /api/v1/integrations/mh-core/outbox/events/<event_id>
```

Las respuestas no contienen payloads, nombres, correos, teléfonos, referencias ni secretos.

## Piloto real controlado

1. Crea una reservación ordinaria desde el portal con la nota `PILOTO CANAL MH — NO CONTACTAR`.
2. Obtén el UUID desde `latest_event.event_id` en el endpoint de estado.
3. Espera a que el evento quede `published`.
4. Confirma el mismo UUID en el endpoint protegido de MH-Core.
5. Reenvía el UUID solo mediante el mecanismo normal de reintento; MH-Core debe conservar una única fila.

También puede ejecutarse el verificador sin escribir nuevos datos:

```powershell
$env:BACKEND_URL = "https://c-ejixhole-backend.onrender.com"
$env:BACKEND_ADMIN_TOKEN = "<token temporal de administrador>"
$env:MH_CORE_URL = "https://<host-mh-core>"
$env:MH_CORE_API_KEY = "<api key privada>"
python scripts/verify_event_channel.py <event_id>
```

El comando correcto termina con `CANAL VERIFICADO`. Nunca guardes esos valores en Git ni los pegues en capturas.

## Criterio de cierre

- backend y MH-Core desplegados con las mismas versiones fusionadas;
- worker activo como proceso independiente;
- volumen persistente configurado en MH-Core;
- secretos distintos y coincidentes entre emisor/receptor;
- evento `pending → processing → published`;
- `unique_record: true` en MH-Core;
- cero eventos nuevos en `dead_letter`.

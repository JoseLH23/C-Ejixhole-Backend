# Runbook — Respaldo y restauración de PostgreSQL

## Objetivo

Recuperar la base operacional de EjiXhole de forma verificable, sin exponer credenciales ni restaurar accidentalmente sobre producción.

## Objetivos iniciales

- **RPO operativo inicial:** máximo 24 horas de datos.
- **RTO operativo inicial:** máximo 4 horas para recuperar el servicio.
- **Objetivo posterior:** RPO de 1 hora y RTO de 2 horas cuando el proveedor y el volumen lo justifiquen.

Estos objetivos solo se consideran cumplidos cuando existen copias automáticas fuera del servidor principal y una restauración real ha sido probada.

## Requisitos

- `pg_dump`, `pg_restore` y `psql` compatibles con la versión del servidor.
- `DATABASE_URL` para el origen.
- Una base destino aislada y vacía para los simulacros.
- Espacio suficiente y almacenamiento cifrado fuera del servidor principal.

## Crear un respaldo

```powershell
$env:DATABASE_URL = "postgresql://usuario:clave@host:5432/ejixhole"
python scripts/database_backup.py --output-dir backups --prefix ejixhole
```

Se crean dos archivos:

- `*.dump`: respaldo PostgreSQL en formato custom.
- `*.manifest.json`: fecha, tamaño, versión de herramienta y checksum SHA-256.

Nunca debe considerarse válida una copia sin su manifiesto.

## Verificar y restaurar en un ambiente aislado

```powershell
$env:RESTORE_DATABASE_URL = "postgresql://usuario:clave@host:5432/ejixhole_restore_test"
python scripts/database_restore.py `
  --backup backups/ejixhole-AAAAMMDDTHHMMSSZ.dump `
  --confirm-database-name ejixhole_restore_test
```

La herramienta:

1. verifica nombre, tamaño y SHA-256;
2. exige confirmar exactamente la base destino;
3. bloquea nombres que parezcan productivos salvo autorización explícita;
4. restaura con `--exit-on-error`;
5. comprueba que exista una versión Alembic.

## Simulacro obligatorio

Cada mes:

1. descargar una copia reciente desde el proveedor;
2. restaurarla en una base aislada;
3. ejecutar `alembic current`;
4. ejecutar tests de lectura y smoke tests del backend;
5. comparar conteos de tablas y entidades críticas;
6. registrar duración, errores y resultado;
7. eliminar de forma segura el ambiente temporal.

GitHub Actions ejecuta además un simulacro sintético semanal mediante `DR - Backup and restore smoke`. Este check demuestra que las herramientas y el esquema siguen siendo restaurables, pero no sustituye la restauración mensual de una copia real.

## Validaciones posteriores

- `/` responde como liveness.
- `/api/v1/health/ready` confirma dependencias.
- La tabla `alembic_version` coincide con la versión esperada.
- Se pueden consultar usuarios, servicios, reservaciones y pagos.
- Las restricciones de solapamiento e idempotencia siguen activas.
- No se envían correos ni acciones externas durante el simulacro.

## Restauración de producción

Solo durante un incidente declarado:

1. detener escrituras o colocar la aplicación en mantenimiento;
2. confirmar el punto de recuperación con el propietario;
3. crear una copia adicional del estado dañado antes de reemplazarlo;
4. restaurar primero en un destino aislado;
5. validar integridad y versión;
6. realizar el cambio controlado;
7. ejecutar smoke tests;
8. documentar pérdida de datos estimada y duración;
9. rotar credenciales si el incidente las pudo exponer.

No uses `--allow-production` sin aprobación explícita y sin una copia previa del estado actual.

## Retención recomendada

- 7 copias diarias.
- 4 copias semanales.
- 6 copias mensuales.
- Cifrado en tránsito y reposo.
- Al menos una copia en una ubicación o proveedor independiente.

## Evidencia del simulacro

Registrar:

- fecha y responsable;
- identificador de la copia;
- fecha contenida en el respaldo;
- checksum;
- tiempo de descarga;
- tiempo de restauración;
- resultado de migraciones y smoke tests;
- incidencias encontradas;
- acciones correctivas y fecha objetivo.

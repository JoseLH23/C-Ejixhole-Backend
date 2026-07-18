# Respaldo y restauración de PostgreSQL

## Objetivo

Recuperar la base operacional de EjiXhole de forma verificable y evitar restauraciones accidentales sobre un destino equivocado.

## Objetivos iniciales

- **RPO:** 24 horas.
- **RTO:** 4 horas.
- **Meta posterior:** RPO de 1 hora y RTO de 2 horas.

Estos objetivos se consideran comprobados únicamente después de restaurar una copia real en un ambiente aislado y medir el ejercicio.

## Requisitos

- `pg_dump`, `pg_restore` y `psql` compatibles con el servidor.
- `DATABASE_URL` configurada en el ambiente.
- Una base aislada y vacía para pruebas de recuperación.
- Almacenamiento cifrado fuera del servidor principal.

## Crear respaldo

```powershell
$env:DATABASE_URL = "postgresql://<usuario>@<host>:5432/<base>"
python scripts/database_backup.py --output-dir backups --prefix ejixhole
```

Se generan:

- un archivo `*.dump` en formato custom de PostgreSQL;
- un archivo `*.manifest.json` con fecha, tamaño, versión de herramienta y checksum SHA-256.

Una copia sin su manifiesto no debe considerarse verificada.

## Restaurar en ambiente aislado

```powershell
$env:RESTORE_DATABASE_URL = "postgresql://<usuario>@<host>:5432/ejixhole_restore_test"
python scripts/database_restore.py `
  --backup backups/ejixhole-AAAAMMDDTHHMMSSZ.dump `
  --confirm-database-name ejixhole_restore_test
```

La herramienta:

1. verifica nombre, tamaño y checksum;
2. exige confirmar el nombre exacto del destino;
3. bloquea nombres que parezcan productivos salvo autorización expresa;
4. restaura con detención inmediata ante errores;
5. comprueba la versión de Alembic restaurada.

## Simulacro mensual

1. obtener una copia reciente del proveedor;
2. restaurarla en una base aislada;
3. comprobar `alembic current`;
4. ejecutar pruebas de lectura y smoke tests;
5. comparar tablas y entidades críticas;
6. registrar duración, resultado y acciones correctivas;
7. eliminar el ambiente temporal.

GitHub Actions ejecuta además un ejercicio sintético semanal mediante `DR - Restore check`. Este control verifica herramientas y esquema, pero no sustituye el ejercicio mensual con una copia real.

## Validaciones posteriores

- liveness y readiness correctos;
- versión Alembic esperada;
- consultas de usuarios, servicios, reservaciones y pagos;
- restricciones de solapamiento e idempotencia activas;
- acciones externas deshabilitadas durante el ejercicio.

## Incidente real

1. detener escrituras cuando sea necesario;
2. conservar una copia adicional del estado afectado;
3. seleccionar el punto de recuperación con el propietario;
4. restaurar primero en un destino aislado;
5. validar integridad y versión;
6. realizar el cambio controlado;
7. ejecutar smoke tests;
8. registrar duración y pérdida máxima posible;
9. revisar accesos y configuración si el incidente pudo afectarlos.

## Retención recomendada

- 7 copias diarias;
- 4 semanales;
- 6 mensuales;
- cifrado en tránsito y reposo;
- al menos una copia en una ubicación independiente.

## Evidencia

Registrar fecha, responsable, identificador de copia, checksum, duración, resultado de migraciones, smoke tests y acciones correctivas. No almacenar datos personales ni archivos de respaldo dentro del repositorio.

# Respaldo y restauración de PostgreSQL

Este procedimiento protege la base de datos de EjiXhole y comprueba que un respaldo realmente puede restaurarse.

## Alcance

- El respaldo usa el formato personalizado de PostgreSQL (`pg_dump --format=custom`).
- No incluye propietarios ni privilegios del proveedor original.
- Cada respaldo puede generar un checksum SHA-256 para detectar corrupción.
- La restauración exige confirmación explícita y verifica la tabla `alembic_version`.
- GitHub Actions prueba automáticamente respaldo y restauración contra una base PostgreSQL desechable.

## Requisitos en Windows

Debes tener disponibles estos comandos en PowerShell:

```powershell
pg_dump --version
pg_restore --version
psql --version
```

Normalmente se instalan junto con PostgreSQL. Si PowerShell no los encuentra, agrega al `PATH` la carpeta similar a:

```text
C:\Program Files\PostgreSQL\17\bin
```

## Crear un respaldo

Nunca escribas la URL real en un archivo versionado ni la pegues en GitHub.

```powershell
cd C:\Ejixhole-Backend

$env:DATABASE_URL = "postgresql://USUARIO:CONTRASENA@HOST:PUERTO/BASE?sslmode=require"

.\scripts\backup_postgres.ps1
```

Los archivos se guardan en `backups/`:

```text
ejixhole-AAAAmmdd-HHMMSS.dump
ejixhole-AAAAmmdd-HHMMSS.dump.sha256
```

Al terminar, elimina la variable de la terminal:

```powershell
Remove-Item Env:DATABASE_URL
```

## Probar la restauración

La prueba debe hacerse contra una base temporal vacía. No uses la base de producción.

1. Crea una base temporal, por ejemplo `ejixhole_restore_test`.
2. Configura su URL en `RESTORE_DATABASE_URL`.
3. Ejecuta el script con confirmación explícita.

```powershell
cd C:\Ejixhole-Backend

$env:RESTORE_DATABASE_URL = "postgresql://USUARIO:CONTRASENA@HOST:PUERTO/ejixhole_restore_test?sslmode=require"

.\scripts\restore_postgres.ps1 `
  -BackupFile ".\backups\ejixhole-AAAAmmdd-HHMMSS.dump" `
  -ConfirmRestore
```

El script valida el checksum cuando existe y consulta la revisión restaurada de Alembic.

Después elimina la variable:

```powershell
Remove-Item Env:RESTORE_DATABASE_URL
```

## Verificación adicional recomendada

Compara cantidades de registros entre la base original y la temporal:

```sql
SELECT COUNT(*) FROM clientes;
SELECT COUNT(*) FROM reservaciones;
SELECT COUNT(*) FROM pagos;
SELECT COUNT(*) FROM movimientos_caja;
SELECT version_num FROM alembic_version;
```

La restauración se considera aprobada cuando:

- el checksum coincide;
- `pg_restore` termina sin errores;
- existe una revisión en `alembic_version`;
- las cantidades principales coinciden;
- el backend puede conectarse a la base restaurada en un entorno controlado.

## Reglas de seguridad

- No restaures sobre producción para hacer una prueba.
- No guardes URLs, contraseñas ni archivos `.dump` en Git.
- Guarda al menos una copia fuera del proveedor de base de datos.
- Cifra el almacenamiento donde se conserven respaldos reales.
- Restringe el acceso a los respaldos igual que a la base de datos.
- Registra fecha, responsable y resultado de cada prueba de restauración.

## Retención propuesta

Cuando se automaticen los respaldos reales:

- diarios: conservar 7 días;
- semanales: conservar 4 semanas;
- mensuales: conservar 6 meses.

Esta política es una propuesta inicial y debe ajustarse al volumen de datos, costo y obligaciones legales.

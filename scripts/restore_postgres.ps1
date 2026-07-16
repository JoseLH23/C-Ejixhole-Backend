[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,

    [string]$TargetDatabaseUrl = $env:RESTORE_DATABASE_URL,

    [switch]$ConfirmRestore,
    [switch]$SkipChecksum
)

$ErrorActionPreference = "Stop"

function ConvertTo-LibpqUrl {
    param([Parameter(Mandatory = $true)][string]$Url)

    return $Url -replace '^postgresql\+[^:]+://', 'postgresql://'
}

if (-not $ConfirmRestore) {
    throw "Restauración cancelada. Usa -ConfirmRestore únicamente contra una base temporal o una base que realmente quieras reemplazar."
}

if ([string]::IsNullOrWhiteSpace($TargetDatabaseUrl)) {
    throw "RESTORE_DATABASE_URL no está configurada. Define `$env:RESTORE_DATABASE_URL o usa -TargetDatabaseUrl."
}

$backupPath = (Resolve-Path -LiteralPath $BackupFile).Path
$pgRestore = Get-Command pg_restore -ErrorAction SilentlyContinue
$psql = Get-Command psql -ErrorAction SilentlyContinue

if (-not $pgRestore) {
    throw "No se encontró pg_restore. Instala las herramientas cliente de PostgreSQL y agrega su carpeta bin al PATH."
}

if (-not $psql) {
    throw "No se encontró psql. Instala las herramientas cliente de PostgreSQL y agrega su carpeta bin al PATH."
}

if (-not $SkipChecksum) {
    $checksumPath = "$backupPath.sha256"
    if (Test-Path -LiteralPath $checksumPath) {
        $expected = ((Get-Content -LiteralPath $checksumPath -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $backupPath).Hash.ToLowerInvariant()
        if ($actual -ne $expected) {
            throw "El checksum SHA-256 no coincide. No se restaurará un respaldo posiblemente dañado."
        }
        Write-Host "Checksum SHA-256 verificado."
    }
    else {
        Write-Warning "No existe archivo .sha256. Continúa solo porque no hay checksum disponible."
    }
}

$libpqUrl = ConvertTo-LibpqUrl -Url $TargetDatabaseUrl
Write-Host "Restaurando respaldo en la base de destino..."

$arguments = @(
    "--clean"
    "--if-exists"
    "--no-owner"
    "--no-privileges"
    "--exit-on-error"
    "--dbname=$libpqUrl"
    $backupPath
)

& $pgRestore.Source @arguments
if ($LASTEXITCODE -ne 0) {
    throw "pg_restore terminó con código $LASTEXITCODE. Revisa la base de destino antes de volver a intentar."
}

$revision = & $psql.Source $libpqUrl --tuples-only --no-align --set ON_ERROR_STOP=1 --command "SELECT version_num FROM alembic_version LIMIT 1;"
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($revision | Out-String))) {
    throw "La restauración terminó, pero no se pudo verificar alembic_version."
}

Write-Host "Restauración verificada correctamente."
Write-Host "Revisión Alembic restaurada: $($revision.Trim())"

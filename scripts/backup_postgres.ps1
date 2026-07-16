[CmdletBinding()]
param(
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [string]$OutputDirectory = (Join-Path (Split-Path -Parent $PSScriptRoot) "backups"),
    [switch]$SkipChecksum
)

$ErrorActionPreference = "Stop"

function ConvertTo-LibpqUrl {
    param([Parameter(Mandatory = $true)][string]$Url)

    return $Url -replace '^postgresql\+[^:]+://', 'postgresql://'
}

if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
    throw "DATABASE_URL no está configurada. Define `$env:DATABASE_URL o usa -DatabaseUrl."
}

$pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
if (-not $pgDump) {
    throw "No se encontró pg_dump. Instala las herramientas cliente de PostgreSQL y agrega su carpeta bin al PATH."
}

$libpqUrl = ConvertTo-LibpqUrl -Url $DatabaseUrl
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$outputPath = (Resolve-Path -LiteralPath $OutputDirectory).Path
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path $outputPath "ejixhole-$timestamp.dump"

Write-Host "Creando respaldo PostgreSQL..."

$arguments = @(
    "--format=custom"
    "--compress=9"
    "--no-owner"
    "--no-privileges"
    "--file=$backupPath"
    $libpqUrl
)

& $pgDump.Source @arguments
if ($LASTEXITCODE -ne 0) {
    Remove-Item -LiteralPath $backupPath -ErrorAction SilentlyContinue
    throw "pg_dump terminó con código $LASTEXITCODE. El respaldo no es válido."
}

if (-not (Test-Path -LiteralPath $backupPath) -or (Get-Item -LiteralPath $backupPath).Length -eq 0) {
    throw "El archivo de respaldo no fue creado o está vacío."
}

if (-not $SkipChecksum) {
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $backupPath).Hash.ToLowerInvariant()
    $checksumPath = "$backupPath.sha256"
    "$hash  $(Split-Path -Leaf $backupPath)" | Set-Content -LiteralPath $checksumPath -Encoding ascii -NoNewline
    Write-Host "Checksum SHA-256: $checksumPath"
}

$file = Get-Item -LiteralPath $backupPath
Write-Host "Respaldo creado correctamente: $($file.FullName)"
Write-Host "Tamaño: $([math]::Round($file.Length / 1MB, 2)) MB"

$file

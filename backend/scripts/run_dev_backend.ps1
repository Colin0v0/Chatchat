param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8050,
    [switch]$SkipMigrate,
    [switch]$MigrateLegacySqlite,
    [string]$SourceSqlite = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-CheckedPython {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: python $($Arguments -join ' ')"
    }
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Split-Path -Parent $ScriptDir

Push-Location $BackendDir
try {
    $env:CHATCHAT_ENV = "dev.windows"

    if ($MigrateLegacySqlite) {
        Write-Host "[chatchat] migrating legacy SQLite into dev PostgreSQL..." -ForegroundColor Cyan
        $migrationArgs = @("scripts/migrate_sqlite_to_database.py", "--truncate-target")
        if ($SourceSqlite.Trim()) {
            $migrationArgs += @("--source-sqlite", $SourceSqlite)
        }
        Invoke-CheckedPython -Arguments $migrationArgs
    }
    else {
        Write-Host "[chatchat] bootstrapping dev PostgreSQL schema..." -ForegroundColor Cyan
        Invoke-CheckedPython -Arguments @("scripts/bootstrap_dev_database.py")
    }

    if (-not $SkipMigrate) {
        Write-Host "[chatchat] applying Alembic migrations..." -ForegroundColor Cyan
        Invoke-CheckedPython -Arguments @("-m", "alembic", "upgrade", "head")
    }

    Write-Host "[chatchat] starting backend..." -ForegroundColor Cyan
    Invoke-CheckedPython -Arguments @("app.py", "--reload", "--host", $BindHost, "--port", "$Port")
}
finally {
    Pop-Location
}

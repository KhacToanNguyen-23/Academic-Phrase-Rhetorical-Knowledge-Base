param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("be", "fe", "worker", "down")]
    [string]$Target
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-DevTool {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$LongRunning
    )

    & $Name @Arguments
    if ($LASTEXITCODE -ne 0 -and -not $LongRunning) {
        throw "$Name exited with code $LASTEXITCODE"
    }
}

switch ($Target) {
    "be" {
        Invoke-DevTool docker @("compose", "up", "-d", "--wait", "postgres")
        Invoke-DevTool uv @("sync", "--directory", "apps/backend")
        Invoke-DevTool uv @("run", "--directory", "apps/backend", "alembic", "-c", "alembic.ini", "upgrade", "head")
        Invoke-DevTool uv @("run", "--directory", "apps/backend", "python", "-m", "aprkb.seeds.load")
        Invoke-DevTool uv @("run", "--directory", "apps/backend", "uvicorn", "aprkb.api.main:app", "--reload") -LongRunning
    }
    "fe" {
        if (-not (Test-Path "apps/web/node_modules")) {
            Invoke-DevTool pnpm @("--dir", "apps/web", "install")
        }
        Invoke-DevTool pnpm @("--dir", "apps/web", "run", "dev") -LongRunning
    }
    "worker" {
        Invoke-DevTool uv @("run", "--directory", "apps/backend", "python", "-m", "aprkb.worker.runner") -LongRunning
    }
    "down" {
        Invoke-DevTool docker @("compose", "down")
    }
}

$ErrorActionPreference = "Stop"

$databaseUrl = $env:TEST_DATABASE_URL
if ([string]::IsNullOrWhiteSpace($databaseUrl)) {
    throw "Set TEST_DATABASE_URL in this PowerShell process before running backend tests."
}

$match = [regex]::Match(
    $databaseUrl,
    '^postgres(?:ql)?(?:\+[^:]+)?://[^/]+/(?<database>[^?/#]+)(?:\?.*)?$'
)
if (-not $match.Success) {
    throw "TEST_DATABASE_URL must be a PostgreSQL URL."
}
if ([uri]::UnescapeDataString($match.Groups["database"].Value) -ne "aprkb_test") {
    throw "TEST_DATABASE_URL must target the dedicated aprkb_test database."
}

Push-Location (Join-Path $PSScriptRoot "../apps/backend")
try {
    & uv run pytest
    if ($LASTEXITCODE -ne 0) {
        throw "Backend tests failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

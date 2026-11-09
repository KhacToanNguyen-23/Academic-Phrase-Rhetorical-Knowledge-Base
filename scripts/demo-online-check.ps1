param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$WebUrl = "http://127.0.0.1:5173"
)

$ErrorActionPreference = "Stop"

function Assert-Check {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
    Write-Host "PASS: $Message" -ForegroundColor Green
}

$web = Invoke-WebRequest -Uri $WebUrl -TimeoutSec 10 -UseBasicParsing
Assert-Check ($web.StatusCode -eq 200) "Web app responds at $WebUrl"

$docs = Invoke-WebRequest -Uri "$BaseUrl/docs" -TimeoutSec 10 -UseBasicParsing
Assert-Check ($docs.StatusCode -eq 200) "API docs respond at $BaseUrl/docs"

$health = Invoke-RestMethod -Uri "$BaseUrl/v1/health" -TimeoutSec 10
Assert-Check (
    $health.status -eq "ok" -and $health.database -eq "ok"
) "API and database health check pass"

$webRoot = $WebUrl.TrimEnd('/')
$proxyHealth = Invoke-RestMethod -Uri "$webRoot/v1/health" -TimeoutSec 10
Assert-Check (
    $proxyHealth.status -eq "ok" -and $proxyHealth.database -eq "ok"
) "Web dev server proxies API requests to the backend"

$demoSession = Invoke-RestMethod `
    -Method Post `
    -Uri "$webRoot/v1/auth/demo-session" `
    -TimeoutSec 30
$identity = Invoke-RestMethod `
    -Uri "$webRoot/v1/auth/me" `
    -Headers @{ "X-API-Key" = $demoSession.api_key } `
    -TimeoutSec 10
Assert-Check ($identity.role -eq "curator") "Quick demo signs in as a curator"

$recommendation = Invoke-RestMethod `
    -Method Post `
    -Uri "$BaseUrl/v1/recommendations" `
    -ContentType "application/json" `
    -Body '{"limit":3}'
Assert-Check ($recommendation.items.Count -gt 0) "Seeded demo phrases are recommended"

$renderable = $recommendation.items |
    Where-Object { $_.canonical_frame -match '\{[A-Za-z][A-Za-z0-9_]*\}' } |
    Select-Object -First 1
Assert-Check ($null -ne $renderable) "A recommended phrase has fillable slots"

$slots = @{}
foreach ($match in [regex]::Matches($renderable.canonical_frame, '\{([A-Za-z][A-Za-z0-9_]*)\}')) {
    $slots[$match.Groups[1].Value] = "demo phrase."
}
$renderBody = @{
    recommendation_id = $recommendation.recommendation_id
    pattern_version_id = $renderable.pattern_version_id
    slots = $slots
} | ConvertTo-Json -Depth 4
$rendered = Invoke-RestMethod `
    -Method Post `
    -Uri "$BaseUrl/v1/render" `
    -ContentType "application/json" `
    -Body $renderBody
Assert-Check ($rendered.text -match "demo phrase\.") "Phrase slots render"
Assert-Check (
    @($rendered.warnings | Where-Object { $_ -like "Slot values ending with sentence punctuation*" }).Count -gt 0
) "Render warns when slot values look like full sentences"

$query = "unlikelyterm$([guid]::NewGuid().ToString('N'))"
$emptyResult = Invoke-RestMethod `
    -Method Post `
    -Uri "$BaseUrl/v1/recommendations" `
    -ContentType "application/json" `
    -Body (@{ query = $query } | ConvertTo-Json)
Assert-Check ($emptyResult.items.Count -eq 0) "Unknown search term returns no phrases"
Assert-Check (
    @($emptyResult.warnings | Where-Object { $_ -like "No approved phrases match the query*" }).Count -gt 0
) "Empty search explains why no phrases matched"

$validation = Invoke-RestMethod `
    -Method Post `
    -Uri "$BaseUrl/v1/validate" `
    -ContentType "application/json" `
    -Body '{"text":"This proves the intervention caused the {outcome}.","claim_type":"causal","evidence_level":"single_study","epistemic_strength":"absolute"}'
Assert-Check (-not $validation.complete) "Validation reports unavailable checks as incomplete"
Assert-Check (
    @($validation.warnings | Where-Object { $_ -like "*{outcome}*" }).Count -gt 0
) "Validation warns about an unfilled template placeholder"

$unsupportedNumber = Invoke-RestMethod `
    -Method Post `
    -Uri "$BaseUrl/v1/validate" `
    -ContentType "application/json" `
    -Body '{"text":"The study improved accuracy by 99.9%.","claim_type":"descriptive","evidence_level":"single_study"}'
$unsupportedV03 = $unsupportedNumber.rules | Where-Object { $_.code -eq "V03" } | Select-Object -First 1
Assert-Check ($unsupportedV03.severity -eq "block") "V03 blocks a number absent from the supplied context"

$supportedNumber = Invoke-RestMethod `
    -Method Post `
    -Uri "$BaseUrl/v1/validate" `
    -ContentType "application/json" `
    -Body '{"text":"The study improved accuracy by 99.9%.","claim_type":"descriptive","evidence_level":"single_study","context":"The study reported a 99.9% accuracy improvement."}'
$supportedV03 = $supportedNumber.rules | Where-Object { $_.code -eq "V03" } | Select-Object -First 1
Assert-Check ($supportedV03.severity -eq "pass") "V03 accepts a number present in supporting context"

Write-Host ""
Write-Host "Demo checks completed. Open $WebUrl to test the Writer UI." -ForegroundColor Cyan
Write-Host "Note: Quick demo rotates the local curator key; recommendation checks create normal local logs."

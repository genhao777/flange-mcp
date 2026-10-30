param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtual environment not found: $Python"
}

Set-Location -LiteralPath $Root
$env:PYTHONPATH = Join-Path $Root "src"

Write-Host "[1/5] day1 geometry acceptance"
& $Python (Join-Path $Root "scripts\day1_baseline.py") *> $null
if ($LASTEXITCODE -ne 0) { throw "day1 acceptance failed" }

Write-Host "[2/5] day2 parameter and invalid-input acceptance"
& $Python (Join-Path $Root "scripts\day2_parameter_cases.py") *> $null
if ($LASTEXITCODE -ne 0) { throw "day2 acceptance failed" }

Write-Host "[3/5] projection topology regression"
& $Python (Join-Path $Root "scripts\projection_regression.py")
if ($LASTEXITCODE -ne 0) { throw "projection regression failed" }

Write-Host "[4/5] Python compile check"
& $Python -m compileall -q (Join-Path $Root "src") (Join-Path $Root "scripts")
if ($LASTEXITCODE -ne 0) { throw "compile check failed" }

Write-Host "[5/5] MCP end-to-end smoke test"
& $Python (Join-Path $Root "scripts\mcp_smoke.py")
if ($LASTEXITCODE -ne 0) { throw "MCP smoke test failed" }

Write-Host "Release verification passed. Latest outputs are under $Root\out."

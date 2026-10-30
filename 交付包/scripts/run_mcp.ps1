param(
    [switch]$SmokeTest
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtual environment not found. Run: python -m venv .venv"
}

$env:PYTHONPATH = Join-Path $Root "src"
Set-Location -LiteralPath $Root

if ($SmokeTest) {
    & $Python (Join-Path $Root "scripts\mcp_smoke.py")
} else {
    & $Python -m flange_mcp.server
}


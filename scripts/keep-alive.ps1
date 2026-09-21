$ErrorActionPreference = "SilentlyContinue"
# Keeps the API (:8080) and web dev server (:3000) alive.
# The sandbox on this machine periodically reaps detached processes, so we re-launch them.

function Test-Url([string]$url, [int]$timeoutSec = 6) {
  try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeoutSec | Out-Null; return $true }
  catch { return $false }
}

$apiScript = "C:\Users\Mistledan\Downloads\ai-trader\scripts\api-run.ps1"
$webScript = "C:\Users\Mistledan\Downloads\ai-trader\scripts\web-run.ps1"

while ($true) {
  if (-not (Test-Url "http://127.0.0.1:8080/api/v1/health")) {
    $py = Get-Process python -ErrorAction SilentlyContinue
    if (-not $py) {
      Start-Process powershell -ArgumentList "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", $apiScript
    }
  }
  if (-not (Test-Url "http://127.0.0.1:3000/")) {
    $node = Get-Process node -ErrorAction SilentlyContinue
    if (-not $node) {
      Start-Process powershell -ArgumentList "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", $webScript
    }
  }
  Start-Sleep -Seconds 20
}
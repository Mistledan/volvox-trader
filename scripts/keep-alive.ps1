$ErrorActionPreference = "SilentlyContinue"
# Keeps Volvox Trader alive: API on :8080 and web dev server on :3000.
# This sandbox reaps detached processes, so we relaunch whatever dies.
# Port checks are specific to our services (other projects also run python/node).

function Test-Up([int]$port) {
  return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

$apiScript = "C:\Users\Mistledan\Downloads\ai-trader\scripts\api-run.ps1"
$webScript = "C:\Users\Mistledan\Downloads\ai-trader\scripts\web-run.ps1"
$apiLast = [datetime]::MinValue
$webLast = [datetime]::MinValue

while ($true) {
  $now = Get-Date
  if (-not (Test-Up 8080) -and ($now - $apiLast).TotalSeconds -gt 45) {
    Start-Process powershell -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", $apiScript
    $apiLast = $now
  }
  if (-not (Test-Up 3000) -and ($now - $webLast).TotalSeconds -gt 30) {
    Start-Process powershell -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", $webScript
    $webLast = $now
  }
  Start-Sleep -Seconds 15
}
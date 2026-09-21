$ErrorActionPreference = "SilentlyContinue"
# One-pass: ensure the Volvox Trader API (:8080) and web dev server (:3000) are up.
# Run by Windows Task Scheduler every minute so the services survive this
# environment's reaping of shell-spawned background processes.
# Guards prevent overlapping starts (which caused duplicate-process contention).

function Test-Up([int]$port) {
  return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Has-Process([string]$pattern) {
  return [bool](Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='node.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match $pattern })
}

$root = "C:\Users\Mistledan\Downloads\ai-trader"

if (-not (Test-Up 8080) -and -not (Has-Process 'ai_trader\.server')) {
  Start-Process powershell -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", "$root\scripts\api-run.ps1"
}
if (-not (Test-Up 3000) -and -not (Has-Process 'ai-trader\\web')) {
  Start-Process powershell -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", "$root\scripts\web-run.ps1"
}
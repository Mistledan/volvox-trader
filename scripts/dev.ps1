# Volvox Trader - run the whole stack (API + web) and keep it alive.
# Usage:  right-click > Run with PowerShell,  OR  powershell -File scripts\dev.ps1
#
# Keep this window open: while it runs, both servers stay up, and either one is
# restarted automatically if it stops. Close the window to shut everything down.

$ErrorActionPreference = "SilentlyContinue"
Write-Host "Starting Volvox Trader (API :8080 + web :3000)... keep this window open." -ForegroundColor Cyan

& "$PSScriptRoot\ensure-up.ps1"

while ($true) {
  if (-not [bool](Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue)) {
    Write-Host "[$(Get-Date -Format HH:mm:ss)] API down - restarting..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", "$PSScriptRoot\api-run.ps1"
  }
  if (-not [bool](Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue)) {
    Write-Host "[$(Get-Date -Format HH:mm:ss)] web down - restarting..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", "$PSScriptRoot\web-run.ps1"
  }
  Start-Sleep -Seconds 15
}
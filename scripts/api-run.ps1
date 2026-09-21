$ErrorActionPreference = "Stop"
Set-Location "C:\Users\Mistledan\Downloads\ai-trader"
& ".venv\Scripts\python.exe" -m ai_trader.server *> "C:\Users\Mistledan\Downloads\ai-trader\logs\server_run.log"
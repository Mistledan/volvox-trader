$ErrorActionPreference = "Stop"
Set-Location "C:\Users\Mistledan\Downloads\ai-trader\web"
& "C:\Program Files\nodejs\node.exe" "C:\Users\Mistledan\Downloads\ai-trader\web\node_modules\vite\bin\vite.js" --host --port 3005 *> "C:\Users\Mistledan\Downloads\ai-trader\logs\web_run.log"
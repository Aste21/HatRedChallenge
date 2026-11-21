<#
.SYNOPSIS
  Starts every service of the Autonomous CFO locally, each in its own window.

.DESCRIPTION
  forecast service  account-prediction/                 http://127.0.0.1:8081
  instrument agent  instrument_recommendation_agent/    http://127.0.0.1:8082
  news service      news/                               http://127.0.0.1:8083
  backend           backend/                            http://127.0.0.1:8000
  frontend          frontend/                           http://localhost:5173

  LLM settings (LLM_BASE_URL, LLM_API_KEY, LLM_MODEL) are read from backend/.env and passed to every
  service under the variable names it expects. Each Python service needs its virtualenv first:
    cd <service>; py -3 -m venv .venv; .venv\Scripts\python -m pip install -r requirements.txt
  (backend: uv sync, or pip install -e .). URLs use 127.0.0.1 because on Windows "localhost"
  tries IPv6 first and adds about 2 seconds to every call.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\start-local.ps1
#>
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Read-DotEnv([string]$path) {
  $values = @{}
  foreach ($line in Get-Content $path) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') { $values[$Matches[1]] = $Matches[2].Trim() }
  }
  return $values
}

$backendEnv = Read-DotEnv (Join-Path $root 'backend\.env')
$llmBaseUrl = $backendEnv['LLM_BASE_URL'].TrimEnd('/')
$llmApiKey = $backendEnv['LLM_API_KEY']
$llmModel = $backendEnv['LLM_MODEL']
if (-not $llmModel) {
  $models = Invoke-RestMethod -Uri "$llmBaseUrl/models" -Headers @{ Authorization = "Bearer $llmApiKey" }
  $llmModel = $models.data[0].id
}
$newsAdminToken = [guid]::NewGuid().ToString('N')

function Start-Service-Window([string]$title, [string]$directory, [hashtable]$environment, [string]$command) {
  $assignments = ($environment.GetEnumerator() | ForEach-Object { "`$env:$($_.Key) = '$($_.Value)'" }) -join '; '
  $script = "`$Host.UI.RawUI.WindowTitle = '$title'; Set-Location '$directory'; $assignments; $command"
  Start-Process powershell -ArgumentList '-NoExit', '-Command', $script | Out-Null
  Write-Host "Started $title"
}

Start-Service-Window 'forecast service :8081' (Join-Path $root 'account-prediction') @{
  LLM_BASE_URL = $llmBaseUrl; LLM_API_KEY = $llmApiKey; LLM_MODEL = $llmModel
} '.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8081'

Start-Service-Window 'instrument agent :8082' (Join-Path $root 'instrument_recommendation_agent\app') @{
  MODEL_BASE_URL = $llmBaseUrl; MODEL_TOKEN = $llmApiKey; MODEL_ID = $llmModel
} '..\.venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 8082'

Start-Service-Window 'news service :8083' (Join-Path $root 'news') @{
  MODEL_URL = $llmBaseUrl; TOKEN = $llmApiKey; MODEL_NAME = $llmModel
  DB_PATH = 'news.db'; ADMIN_TOKEN = $newsAdminToken; PORT = '8083'
} '.venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 8083'

Start-Service-Window 'backend :8000' (Join-Path $root 'backend') @{
  FORECAST_API_URL = 'http://127.0.0.1:8081'; INSTRUMENT_API_URL = 'http://127.0.0.1:8082'
  NEWS_API_URL = 'http://127.0.0.1:8083'
} '.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000'

Start-Service-Window 'frontend :5173' (Join-Path $root 'frontend') @{
  CHAT_API_URL = 'http://127.0.0.1:8000'; NEWS_API_URL = 'http://127.0.0.1:8083'
} 'npm run dev'

Write-Host ""
Write-Host "Open http://localhost:5173"
Write-Host "News admin token for this session (PUT /sources, POST /fetch on :8083): $newsAdminToken"

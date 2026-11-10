# Start the whole live demo, one window per process. Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File demo\start.ps1            # keep current data
#   powershell -ExecutionPolicy Bypass -File demo\start.ps1 -Reset     # clean schema v1 (before each rehearsal)
#   powershell -ExecutionPolicy Bypass -File demo\start.ps1 -Reset -Replay demo\recordings\binance_trades.jsonl
# ASCII only on purpose: Windows PowerShell 5.1 reads BOM-less files as ANSI.
param([switch]$Reset, [string]$Replay)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root 'venv\Scripts\python.exe'
Set-Location $root

docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Docker is not running. Start Docker Desktop first.' }

Write-Host '[1/4] infrastructure (Postgres, ClickHouse, Redpanda, Debezium)'
docker compose up -d postgres_db clickhouse_db
docker compose -f debezium\docker-compose.yml up -d
$deadline = (Get-Date).AddMinutes(3)
while ($true) {
    try { Invoke-WebRequest -UseBasicParsing http://localhost:8083/connectors -TimeoutSec 3 | Out-Null; break }
    catch { if ((Get-Date) -gt $deadline) { throw 'Debezium Connect not ready after 3 min' }; Start-Sleep 3 }
}

Write-Host '[2/4] demo tables + connector'
if ($Reset) { & $py -m demo.setup --reset } else { & $py -m demo.setup }
if ($LASTEXITCODE -ne 0) { throw 'demo.setup failed' }

function Open-Window($title, $command) {
    Start-Process powershell -WorkingDirectory $root -ArgumentList @(
        '-NoExit', '-Command', "`$Host.UI.RawUI.WindowTitle = '$title'; $command")
}

Write-Host '[3/4] engine backend first, so its Kafka consumer group settles before data flows'
Open-Window 'backend' "& '$py' -m uvicorn api.main:app --port 8000"
Open-Window 'frontend' 'cd frontend; npm run dev'
Start-Sleep 10

Write-Host '[4/4] data flow'
$source = if ($Replay) { "--replay '$Replay'" } else { '' }
Open-Window 'ingestor' "& '$py' -m demo.ingestor $source"
Open-Window 'loader' "& '$py' -m demo.loader"
Open-Window 'naive-loader' "& '$py' -m demo.loader --naive"
Open-Window 'check' "& '$py' -m demo.check --watch"

Write-Host ''
Write-Host 'Wait ~60s for the consumer groups to settle, then open http://localhost:5173 (Live Data Flow).'
Write-Host 'Scenario steps: python -m demo.scenario add_column | widen | rename | narrow | rollback'

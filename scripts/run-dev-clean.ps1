# Purpose: launch the full dev stack from a clean slate for Cypress and manual
# testing. Article V requires UX tests run against this launcher, never against
# a built binary.
#
# ARTICLE II (HIGHEST SEVERITY): this script stops processes only by the exact
# PID it recorded when starting them. It must never match processes by name
# pattern — a wildcard kill here would terminate the agent's own session.

[CmdletBinding()]
param(
    [switch]$SkipPurge,
    [switch]$StopOnly
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$RunDirectory = Join-Path $RepoRoot 'worker\.run'
$PidRegistry = Join-Path $RunDirectory 'dev-stack.pids.json'

function Stop-DevStack {
    <#
    .SYNOPSIS
        Stop every process this script previously started, by recorded PID only.
    #>
    if (-not (Test-Path $PidRegistry)) {
        Write-Host 'No running dev stack recorded.'
        return
    }

    $recorded = Get-Content $PidRegistry -Raw | ConvertFrom-Json
    foreach ($entry in $recorded.PSObject.Properties) {
        $processId = [int]$entry.Value
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($null -eq $process) {
            Write-Host "  $($entry.Name): already stopped (PID $processId)"
            continue
        }
        # Targeted stop by PID — never by name. See the Article II note above.
        Stop-Process -Id $processId -Force -Confirm:$false
        Write-Host "  $($entry.Name): stopped (PID $processId)"
    }
    Remove-Item $PidRegistry -Force
}

if ($StopOnly) {
    Write-Host 'Stopping dev stack...'
    Stop-DevStack
    exit 0
}

Write-Host 'Stopping any previous dev stack...'
Stop-DevStack

New-Item -ItemType Directory -Force -Path $RunDirectory | Out-Null

if (-not $SkipPurge) {
    Write-Host 'Purging local state so runs are reproducible...'
    Get-ChildItem -Path $RunDirectory -Filter '*.sqlite' -ErrorAction SilentlyContinue |
        Remove-Item -Force -Confirm:$false
    $workerStore = Join-Path $RepoRoot 'worker\transcriptboss.sqlite'
    if (Test-Path $workerStore) { Remove-Item $workerStore -Force -Confirm:$false }
}

Write-Host 'Checking required secrets are injected (Article IX)...'
$requiredSecrets = @(
    'OMI_APP_ID',
    'OMI_APP_INTEGRATION_KEY',
    'ANTHROPIC_API_KEY',
    'CONTROL_PLANE_DATABASE_URL'
)
$missing = $requiredSecrets | Where-Object { -not (Test-Path "env:$_") }
if ($missing) {
    Write-Error @"
Missing injected secrets: $($missing -join ', ')

Inject them through the Forge Vault, then source the returned script:
  vault_inject({ secret_names: [$(($requiredSecrets | ForEach-Object { "`"$_`"" }) -join ', ')] })

Secrets must never be written to a file or pasted into this shell.
"@
}

$processIds = @{}

Write-Host 'Starting control plane on http://127.0.0.1:8000 ...'
$controlPlane = Start-Process -PassThru -NoNewWindow -FilePath 'uv' -ArgumentList @(
    'run', '--project', (Join-Path $RepoRoot 'control-plane'),
    'uvicorn', 'transcriptboss_control.api.app:app',
    '--host', '127.0.0.1', '--port', '8000', '--reload'
)
$processIds['control-plane'] = $controlPlane.Id

Write-Host 'Starting worker daemon on http://127.0.0.1:8765 ...'
$worker = Start-Process -PassThru -NoNewWindow -FilePath 'uv' -ArgumentList @(
    'run', '--project', (Join-Path $RepoRoot 'worker'),
    'uvicorn', 'transcriptboss_worker.api.app:app',
    '--host', '127.0.0.1', '--port', '8765', '--reload'
)
$processIds['worker'] = $worker.Id

Write-Host 'Starting web bundles (local :5173, hosted :5174) ...'
$webLocal = Start-Process -PassThru -NoNewWindow -FilePath 'npm' -ArgumentList @(
    '--prefix', (Join-Path $RepoRoot 'web'), 'run', 'dev:local'
)
$processIds['web-local'] = $webLocal.Id

$webHosted = Start-Process -PassThru -NoNewWindow -FilePath 'npm' -ArgumentList @(
    '--prefix', (Join-Path $RepoRoot 'web'), 'run', 'dev:hosted'
)
$processIds['web-hosted'] = $webHosted.Id

$processIds | ConvertTo-Json | Set-Content -Path $PidRegistry -Encoding utf8

Write-Host ''
Write-Host 'Dev stack running. Recorded PIDs:'
$processIds.GetEnumerator() | ForEach-Object { Write-Host "  $($_.Key): $($_.Value)" }
Write-Host ''
Write-Host "Stop it with:  .\scripts\run-dev-clean.ps1 -StopOnly"

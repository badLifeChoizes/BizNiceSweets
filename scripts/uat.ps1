#!/usr/bin/env pwsh
<#
.SYNOPSIS
  One-command setup + launch of the full BizNiceSweets dev stack for human UAT.

.DESCRIPTION
  Brings up the whole stack with a single command using the dev compose overlay:
    - db        PostgreSQL 17 (internal network only, not published to host)
    - api       FastAPI + uvicorn --reload on http://localhost:8000
                (entrypoint auto-runs `alembic upgrade head`; app startup runs the
                 idempotent seeds incl. the SYERP chart-of-accounts)
    - frontend  Vite dev server + HMR on http://localhost:5173

  Everything runs in containers — no local Python/Node install needed. The only
  prerequisite is Podman (preferred) or Docker.

.PARAMETER Fresh
  Reset the database volume (`down -v`) before starting, so migrations and the
  chart-of-accounts seed re-apply from a clean database. Use this for a clean UAT pass.

.PARAMETER Detach
  Start the stack in the background (`up -d`), wait for the API to become healthy,
  open the app in your browser, then return to the prompt. Default (omit) streams
  logs in the foreground; press Ctrl+C to stop.

.PARAMETER Down
  Stop and remove the stack, then exit. Combine with -Fresh to also delete the DB volume.

.PARAMETER NoBrowser
  Do not auto-open the browser (only relevant with -Detach).

.EXAMPLE
  ./scripts/uat.ps1
      Launch the stack in the foreground (logs stream; Ctrl+C stops).

.EXAMPLE
  ./scripts/uat.ps1 -Fresh -Detach
      Reset the DB, launch in the background, wait for health, open the app.

.EXAMPLE
  ./scripts/uat.ps1 -Down
      Stop the stack.
#>
[CmdletBinding()]
param(
  [switch]$Fresh,
  [switch]$Detach,
  [switch]$Down,
  [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

# --- Repo root = parent of this script's directory ---------------------------
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$ComposeFiles = @('compose/compose.yml', 'compose/compose.dev.yml')
$FrontendUrl  = 'http://localhost:5173'
$ApiDocsUrl   = 'http://localhost:8000/docs'
$ApiHealthUrl = 'http://localhost:8000/health/ready'

# --- Resolve a container compose runner (podman preferred per compose docs) ---
function Resolve-Composer {
  if (Get-Command podman-compose -ErrorAction SilentlyContinue) { return @{ Exe = 'podman-compose'; Base = @() } }
  if (Get-Command podman         -ErrorAction SilentlyContinue) { return @{ Exe = 'podman';         Base = @('compose') } }
  if (Get-Command docker         -ErrorAction SilentlyContinue) { return @{ Exe = 'docker';         Base = @('compose') } }
  if (Get-Command docker-compose -ErrorAction SilentlyContinue) { return @{ Exe = 'docker-compose'; Base = @() } }
  throw "No container compose tool found on PATH. Install Podman (recommended) or Docker Desktop."
}
$Composer = Resolve-Composer

$FileArgs = @()
foreach ($f in $ComposeFiles) { $FileArgs += @('-f', $f) }

function Invoke-Composer {
  # NOTE: do NOT name this parameter $Args — it collides with PowerShell's
  # automatic $args variable and the bound value is silently lost.
  param([string[]]$CmdArgs)
  $all = $Composer.Base + $FileArgs + $CmdArgs
  Write-Host "  > $($Composer.Exe) $($all -join ' ')" -ForegroundColor DarkGray
  & $Composer.Exe @all
}

# --- Banner ------------------------------------------------------------------
Write-Host ''
Write-Host '===================================================' -ForegroundColor Cyan
Write-Host ' BizNiceSweets - UAT Launcher' -ForegroundColor Cyan
Write-Host "  runner: $($Composer.Exe)" -ForegroundColor Cyan
Write-Host '===================================================' -ForegroundColor Cyan

# --- Down mode: stop and exit ------------------------------------------------
if ($Down) {
  Write-Host 'Stopping the stack...' -ForegroundColor Yellow
  if ($Fresh) { Invoke-Composer -CmdArgs @('down', '-v') }
  else        { Invoke-Composer -CmdArgs @('down') }
  Write-Host 'Stack stopped.' -ForegroundColor Green
  return
}

# --- Ensure .env exists ------------------------------------------------------
if (-not (Test-Path '.env')) {
  if (Test-Path '.env.example') {
    Copy-Item '.env.example' '.env'
    Write-Warning ".env was missing - created from .env.example. Set POSTGRES_PASSWORD before any non-local use."
  } else {
    throw ".env and .env.example are both missing - cannot configure the stack."
  }
}
$pwLine = Select-String -Path '.env' -Pattern '^POSTGRES_PASSWORD=\S+' -ErrorAction SilentlyContinue
if (-not $pwLine) {
  Write-Warning "POSTGRES_PASSWORD looks empty in .env - the db container may fail to start. Edit .env and set it."
}

# --- Fresh: reset DB volume --------------------------------------------------
if ($Fresh) {
  Write-Host 'Resetting database volume (down -v)...' -ForegroundColor Yellow
  try { Invoke-Composer -CmdArgs @('down', '-v') } catch { Write-Warning "down -v reported: $($_.Exception.Message) (continuing)" }
}

# --- URLs --------------------------------------------------------------------
Write-Host ''
Write-Host 'Once started, open:' -ForegroundColor Green
Write-Host "  App (Vite) : $FrontendUrl" -ForegroundColor Green
Write-Host "  API docs   : $ApiDocsUrl"  -ForegroundColor Green
Write-Host '  Login with the seeded admin user (see .planning / auth seed).' -ForegroundColor Green
Write-Host ''

# --- Detached mode: up -d, wait for health, open browser ---------------------
if ($Detach) {
  Write-Host 'Starting stack in background...' -ForegroundColor Yellow
  Invoke-Composer -CmdArgs @('up', '-d')

  Write-Host 'Waiting for the API to become healthy...' -ForegroundColor Yellow
  $ready = $false
  for ($i = 0; $i -lt 60; $i++) {
    try {
      $resp = Invoke-WebRequest -Uri $ApiHealthUrl -UseBasicParsing -TimeoutSec 3
      if ($resp.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Seconds 2 }
  }
  if ($ready) {
    Write-Host 'API is healthy.' -ForegroundColor Green
    if (-not $NoBrowser) { Start-Process $FrontendUrl }
  } else {
    Write-Warning "API did not report healthy within ~2 min. Check logs: $($Composer.Exe) $(@($Composer.Base + $FileArgs + 'logs' + '-f') -join ' ')"
  }
  Write-Host ''
  Write-Host 'Stack is running in the background.' -ForegroundColor Green
  Write-Host "  View logs : ./scripts/uat.ps1  (foreground)  or  $($Composer.Exe) $(@($Composer.Base + $FileArgs + 'logs' + '-f') -join ' ')" -ForegroundColor Green
  Write-Host '  Stop      : ./scripts/uat.ps1 -Down' -ForegroundColor Green
  return
}

# --- Foreground mode (default): stream logs, Ctrl+C stops --------------------
Write-Host 'Starting stack (foreground). Press Ctrl+C to stop.' -ForegroundColor Yellow
Write-Host ''
Invoke-Composer -CmdArgs @('up')

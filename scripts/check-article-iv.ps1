<#
.SYNOPSIS
    Applies the constitution's Article IV code-quality rules to the files this
    feature adds to the Omi fork — and to nothing else.

.DESCRIPTION
    Omi gates its own pull requests with an analyzer ratchet that counts lint
    occurrences across the whole app and fails on any regression above
    analysis_baseline.json. Our constitution asks for stricter rules than Omi's,
    so turning them on project-wide would either redden that gate or force a
    baseline rewrite across code we did not write — and would sink the upstream
    contribution the plan is aiming for (plan.md D-4).

    So this script scopes our rules to our files. It runs two checks:

      1. dart analyze against analysis_options_transcriptboss.yaml, which turns on
         public_member_api_docs and the correctness rules that matter to an import
         path (unawaited futures, unclosed sinks, uncancelled subscriptions).

      2. The 40-line function limit, which no Dart linter can enforce — the rule
         lives in dart_code_metrics, whose free tier was retired in 2024. That is
         the documented gap Article VII asks for, and scripts/check_function_length.py
         is what fills it.

    Omi's own gate stays Omi's: run omi-fork/app/scripts/analyze_ratchet.sh for that.

.EXAMPLE
    pwsh scripts/check-article-iv.ps1
#>

[CmdletBinding()]
param(
    # The fork's Flutter app. Overridable so the script survives a relocation.
    [string] $AppRoot = (Join-Path $PSScriptRoot '..\omi-fork\app'),

    # Skip the analyzer and run only the function-length gate. Useful on a machine
    # with no Flutter toolchain, which is a real situation during early setup.
    [switch] $SkipAnalyzer
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$appRootResolved = Resolve-Path $AppRoot

# The files this feature owns. Everything else in the fork is Omi's and is held to
# Omi's standard, not ours. Paths that do not exist yet are skipped rather than
# failing, because this script is written before most of them are.
$ownedPaths = @(
    'lib/services/import',
    'lib/services/audio/native_decoder.dart',
    'lib/services/audio_sources/file_import_source.dart',
    'lib/audio_decoder_interface.dart',
    'lib/pages/import',
    'test/unit/import',
    'integration_test/import'
)

$existing = @()
foreach ($relative in $ownedPaths) {
    $full = Join-Path $appRootResolved $relative
    if (Test-Path $full) { $existing += $full }
}

if ($existing.Count -eq 0) {
    Write-Host 'Article IV: no TranscriptBoss files exist in the fork yet — nothing to check.'
    exit 0
}

Write-Host "Article IV: checking $($existing.Count) path(s) under $appRootResolved"
$failed = $false

# --- 1. Scoped analyzer -------------------------------------------------------
if (-not $SkipAnalyzer) {
    $dart = Get-Command dart -ErrorAction SilentlyContinue
    if (-not $dart) {
        Write-Warning 'dart is not on PATH — skipping the analyzer. Install the Flutter SDK to enable it.'
    }
    else {
        $optionsFile = Join-Path $appRootResolved 'analysis_options_transcriptboss.yaml'
        Push-Location $appRootResolved
        try {
            & dart analyze --options=$optionsFile @existing
            if ($LASTEXITCODE -ne 0) { $failed = $true }
        }
        finally { Pop-Location }
    }
}

# --- 2. The 40-line function limit -------------------------------------------
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error 'python is not on PATH — the Article IV function-length gate cannot run.'
    exit 1
}

& python (Join-Path $repoRoot 'scripts/check_function_length.py') @existing
if ($LASTEXITCODE -ne 0) { $failed = $true }

if ($failed) {
    Write-Host ''
    Write-Error 'Article IV checks failed.'
    exit 1
}

Write-Host ''
Write-Host 'Article IV: passed.'
exit 0

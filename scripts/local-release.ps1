# Purpose: build and publish a release entirely from this machine.
#
# ARTICLE VIII: releases NEVER use GitHub Actions. This script builds the worker
# installer and the control-plane image locally, then tags and publishes. No
# step here may push a tag and wait for a hosted runner to build anything.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [switch]$SkipTests,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$DistDirectory = Join-Path $RepoRoot 'dist'

function Invoke-Step {
    param([string]$Name, [scriptblock]$Action)
    Write-Host ''
    Write-Host "==> $Name"
    if ($DryRun) {
        Write-Host '    (dry run — skipped)'
        return
    }
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Version must be semver, e.g. 1.2.3 — got '$Version'"
}

$changelog = Join-Path $RepoRoot 'CHANGELOG.md'
if (-not (Select-String -Path $changelog -Pattern "## \[$([regex]::Escape($Version))\]" -Quiet)) {
    throw "CHANGELOG.md has no entry for $Version. Article VI: the changelog is the source of truth for what changed."
}

if (-not $SkipTests) {
    Invoke-Step 'Worker unit + contract tests' {
        uv run --project (Join-Path $RepoRoot 'worker') pytest tests/unit tests/contract
    }
    Invoke-Step 'Control-plane unit + contract tests' {
        uv run --project (Join-Path $RepoRoot 'control-plane') pytest tests/unit tests/contract
    }
    Invoke-Step 'Web type-check and lint' {
        npm --prefix (Join-Path $RepoRoot 'web') run build
    }
}

New-Item -ItemType Directory -Force -Path $DistDirectory | Out-Null

Invoke-Step 'Build web bundles' {
    npm --prefix (Join-Path $RepoRoot 'web') run build
}

Invoke-Step 'Build worker wheel' {
    uv build --project (Join-Path $RepoRoot 'worker') --out-dir $DistDirectory
}

Invoke-Step 'Build control-plane image' {
    docker build -f (Join-Path $RepoRoot 'control-plane\Dockerfile') `
        -t "transcriptboss-control:$Version" $RepoRoot
}

Invoke-Step "Tag v$Version" {
    git tag -a "v$Version" -m "Release $Version"
}

Invoke-Step "Publish release v$Version" {
    # Article VIII detection order: this script exists, so it owns the release.
    # gh only uploads artifacts already built above — it never triggers a build.
    gh release create "v$Version" `
        --title "v$Version" `
        --notes-file (Join-Path $RepoRoot 'CHANGELOG.md') `
        (Join-Path $DistDirectory '*.whl')
}

Write-Host ''
Write-Host "Release $Version complete. Artifacts in $DistDirectory"

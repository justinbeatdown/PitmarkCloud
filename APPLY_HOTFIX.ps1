param([string]$RepoRoot = (Get-Location).Path)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$files = @(
    "services\discord_hq_blueprint.py",
    "utils\config.py",
    ".env.example",
    "RELEASE_v0.18.4.md"
)

foreach ($rel in $files) {
    $src = Join-Path $here $rel
    $dst = Join-Path $RepoRoot $rel
    $parent = Split-Path -Parent $dst
    if ($parent -and !(Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    Copy-Item -Force $src $dst
    Write-Host "Updated $rel"
}

Write-Host ""
Write-Host "Pitmark full Discord permission model applied."
Write-Host "Commit/push, wait for Render, then run /hq sync."

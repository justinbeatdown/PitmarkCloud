param([string]$RepoRoot = (Get-Location).Path)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$files = @(
    "services\discord_hq_maintenance.py",
    "services\discord_hq_moderation.py",
    "services\discord_hq_service.py",
    "utils\config.py",
    ".env.example",
    "RELEASE_v0.18.5.md"
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
Write-Host "Pitmark Discord HQ QA/cleanup release applied."
Write-Host "Commit/push and wait for Render. No command re-registration is required."
Write-Host "Then run /hq status and use the new buttons."

param([string]$RepoRoot = (Get-Location).Path)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$files = @(
    "services\discord_hq_content.py",
    "services\discord_hq_support.py",
    "services\discord_hq_service.py",
    "utils\config.py",
    ".env.example",
    "RELEASE_v0.18.7.md"
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

# Disable the old one-shot plain-text bootstrap seeder. v0.18.7 content sync
# now owns all launch copy and uses idempotent upserted embeds.
$common = Join-Path $RepoRoot "services\discord_hq_common.py"
if (Test-Path $common) {
    $text = Get-Content $common -Raw
    $start = $text.IndexOf("async def seed_channel(channel: dict[str, Any]) -> None:")
    $endMarker = "async def send_message(channel_id: str, payload: dict[str, Any]) -> dict[str, Any]:"
    $end = $text.IndexOf($endMarker)
    if ($start -ge 0 -and $end -gt $start) {
        $replacement = @"
async def seed_channel(channel: dict[str, Any]) -> None:
    # v0.18.7+: launch copy is owned by discord_hq_content.sync_server_content().
    # Keeping this function as a no-op preserves the bootstrap call site while
    # preventing duplicate plain-text intro messages on fresh servers.
    return


"@
        $text = $text.Substring(0, $start) + $replacement + $text.Substring($end)
        Set-Content -Path $common -Value $text -Encoding UTF8
        Write-Host "Updated services\discord_hq_common.py (disabled legacy seeder)"
    } else {
        Write-Warning "Could not find seed_channel block; common.py was not modified."
    }
}

Write-Host ""
Write-Host "Pitmark Discord launch polish applied."
Write-Host "Commit/push, wait for Render, then run /hq sync or use Refresh Server Content."

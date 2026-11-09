# Docker Desktop 4.35.x on Windows can fail to start after a reboot with:
#   "running OTel manager: removing stale socket: remove ...\Docker\run\userAnalyticsOtlpHttp.sock:
#    The file cannot be accessed by the system."
# The stale AF_UNIX socket cannot be deleted while WSL holds it, so: stop Docker + WSL,
# move the runtime folder aside (Docker recreates it), start Docker again.
# Permanent fix: update Docker Desktop.

$run = Join-Path $env:LOCALAPPDATA "Docker\run"
Get-Process "Docker Desktop", "com.docker.backend", "com.docker.build" -ErrorAction SilentlyContinue | Stop-Process -Force
wsl --shutdown
Start-Sleep -Seconds 3
if (Test-Path $run) {
    $dest = "run.stale-$(Get-Date -Format yyyyMMddHHmm)"
    Rename-Item -LiteralPath $run -NewName $dest
    Write-Host "moved $run aside as $dest (safe to delete later)"
}
Start-Process (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe")
Write-Host "Docker Desktop restarting; run 'docker info' in ~1 minute"

# Creates .env with random local-only passwords (never committed). Safe to re-run: keeps an existing .env.
$envFile = Join-Path $PSScriptRoot "..\.env"
if (Test-Path $envFile) { Write-Host ".env already exists - leaving it alone"; exit 0 }
function New-Pass { -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 20 | ForEach-Object { [char]$_ }) + "!a1" }
@"
CLOUDKIT_MODE=local
MSSQL_SA_PASSWORD=$(New-Pass)
POSTGRES_PASSWORD=lab-local-only
"@ | Set-Content -Encoding utf8 $envFile
Write-Host "wrote $envFile"

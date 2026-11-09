#!/usr/bin/env bash
# Creates .env with random local-only passwords (never committed). Keeps an existing .env.
set -euo pipefail
env_file="$(dirname "$0")/../.env"
[[ -f "$env_file" ]] && { echo ".env already exists - leaving it alone"; exit 0; }
# subshell without pipefail: `head` closing the pipe makes `tr` exit with SIGPIPE by design
pass="$(set +o pipefail; LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20)!a1"
cat >"$env_file" <<EOF
CLOUDKIT_MODE=local
MSSQL_SA_PASSWORD=$pass
POSTGRES_PASSWORD=lab-local-only
EOF
echo "wrote $env_file"

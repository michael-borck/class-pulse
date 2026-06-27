#!/usr/bin/env bash
#
# Generate the long-lived SECRET_KEY for the Docker deploy, exactly ONCE.
#
# Writes SECRET_KEY into ./.env and will NEVER overwrite a value that is already
# there — so you can re-run this safely, and recreating / updating the container
# keeps the same key (existing sessions stay valid).
#
# AI provider settings (AI_PROVIDER/AI_BASE_URL/AI_API_KEY/AI_MODEL) are optional
# and configured by editing .env directly — see .env.example.
#
#   ./scripts/generate-secrets.sh
#
set -euo pipefail

cd "$(dirname "$0")/.."   # operate on the repo root regardless of cwd

ENV_FILE=".env"

# Create .env (mode 0600) if it doesn't exist. Compose auto-loads it for
# ${VAR} interpolation; it is gitignored and must never be committed.
if [ ! -f "$ENV_FILE" ]; then
  ( umask 077 && touch "$ENV_FILE" )
  echo "Created $ENV_FILE"
fi

# SECRET_KEY: signs session cookies. Add only if the line is missing or empty.
if grep -qE '^SECRET_KEY=.' "$ENV_FILE"; then
  echo "SECRET_KEY already present — left unchanged"
else
  printf 'SECRET_KEY=%s\n' "$(openssl rand -hex 32)" >> "$ENV_FILE"
  echo "Wrote a new SECRET_KEY to $ENV_FILE"
fi

chmod 600 "$ENV_FILE"
echo
echo "Done. $ENV_FILE is ready (chmod 600, gitignored)."
echo "Optional: enable AI by setting AI_PROVIDER/AI_BASE_URL/AI_MODEL in $ENV_FILE."

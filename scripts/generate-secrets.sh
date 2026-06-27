#!/usr/bin/env bash
#
# Generate the two long-lived secrets for the Docker deploy, exactly ONCE.
#
# Writes SECRET_KEY and ENCRYPTION_KEY into ./.env, and will NEVER overwrite a
# value that is already there — so you can re-run this safely, and recreating /
# updating the container keeps the same keys (sessions stay valid, stored cloud
# API keys stay decryptable).
#
#   ./scripts/generate-secrets.sh
#
set -euo pipefail

# Always operate on the repo root regardless of where it's called from.
cd "$(dirname "$0")/.."

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

# ENCRYPTION_KEY: a valid Fernet key (encrypts cloud API keys at rest).
# Uses only the Python standard library, so it runs on a host that lacks the
# `cryptography` package. Output == Fernet.generate_key().
if grep -qE '^ENCRYPTION_KEY=.' "$ENV_FILE"; then
  echo "ENCRYPTION_KEY already present — left unchanged"
else
  FERNET="$(python3 -c 'import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
  printf 'ENCRYPTION_KEY=%s\n' "$FERNET" >> "$ENV_FILE"
  echo "Wrote a new ENCRYPTION_KEY to $ENV_FILE"
fi

chmod 600 "$ENV_FILE"
echo
echo "Done. $ENV_FILE is ready (chmod 600, gitignored). Back it up — losing"
echo "ENCRYPTION_KEY means stored API keys can never be decrypted."

#!/usr/bin/env bash
#
# Reset a ClassPulse user's password (e.g. a forgotten admin login).
#
# Passwords are stored as one-way PBKDF2-SHA256 hashes, so they can never be
# read back — only reset. This re-hashes a new password with the app's own
# hashing (guaranteeing a compatible format) and, for convenience, also clears
# the archived flag and marks the account verified so you can log straight in.
#
#   ./scripts/reset-password.sh --list            # show all accounts
#   ./scripts/reset-password.sh <username>        # reset (prompts for password)
#
# By default it runs inside the Docker deploy container. Overrides:
#   COMPOSE_FILE=docker-compose.yml ./scripts/reset-password.sh alice
#   SERVICE=web                     ./scripts/reset-password.sh alice
#   CLASSPULSE_LOCAL=1              ./scripts/reset-password.sh alice   # run python directly (no Docker)
#
set -euo pipefail

cd "$(dirname "$0")/.."   # operate on the repo root regardless of cwd

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.deploy.yml}"
SERVICE="${SERVICE:-web}"

# runner CP_USER CP_PASS <<'PY' ... PY
# Executes the here-doc'd Python with CP_USER/CP_PASS in its environment,
# either inside the container or directly, depending on CLASSPULSE_LOCAL.
runner() {
  local user="$1" pass="$2"
  if [ "${CLASSPULSE_LOCAL:-0}" = "1" ]; then
    CP_USER="$user" CP_PASS="$pass" python -
  else
    docker compose -f "$COMPOSE_FILE" exec -T \
      -e CP_USER="$user" -e CP_PASS="$pass" \
      "$SERVICE" python -
  fi
}

# --- list mode -------------------------------------------------------------
if [ "${1:-}" = "--list" ] || [ "${1:-}" = "-l" ]; then
  runner "" "" <<'PY'
from classpulse import create_app
from classpulse.models import User
app = create_app()
with app.app_context():
    users = User.query.order_by(User.id).all()
    if not users:
        print("No users registered yet.")
    for u in users:
        print(f"  #{u.id:<3} {u.username:<20} {u.email:<30} "
              f"admin={u.is_admin} verified={u.is_verified} archived={u.is_archived}")
PY
  exit 0
fi

USERNAME="${1:-}"
if [ -z "$USERNAME" ]; then
  echo "Usage: $0 <username>        (or --list to see all accounts)" >&2
  exit 2
fi

# --- read the new password (hidden, with confirmation) ---------------------
read -r -s -p "New password for '$USERNAME' (min 10 chars): " PASS1; echo
read -r -s -p "Confirm new password: " PASS2; echo
if [ "$PASS1" != "$PASS2" ]; then
  echo "Passwords do not match. Aborted." >&2
  exit 1
fi
if [ "${#PASS1}" -lt 10 ]; then
  echo "Password must be at least 10 characters (app requirement). Aborted." >&2
  exit 1
fi

# --- reset -----------------------------------------------------------------
# Username and password are passed via env (not argv) so they don't leak into
# the container's process list or your shell history.
runner "$USERNAME" "$PASS1" <<'PY'
import os, sys
from classpulse import create_app
from classpulse.extensions import db
from classpulse.models import User
from classpulse.auth import hash_password

app = create_app()
with app.app_context():
    username = os.environ["CP_USER"]
    u = User.query.filter_by(username=username).first()
    if not u:
        existing = [x.username for x in User.query.all()]
        print(f"No user named '{username}'. Existing users: {existing}", file=sys.stderr)
        sys.exit(1)
    u.password_hash = hash_password(os.environ["CP_PASS"])
    u.is_verified = True
    u.is_archived = False
    db.session.commit()
    print(f"Password reset for '{u.username}' (admin={u.is_admin}). You can log in now.")
PY

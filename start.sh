#!/bin/bash

# ClassPulse Startup Script
# This script sets up the environment and starts the ClassPulse application

set -e  # Exit on any error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "Upgrading pip..."
"$PIP_BIN" install --upgrade pip

# Install dependencies from requirements.txt
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies from requirements.txt..."
    "$PIP_BIN" install -r requirements.txt
else
    echo "Installing dependencies from pyproject.toml..."
    "$PIP_BIN" install -e ".[prod]"
    # Also install any missing dependencies
    "$PIP_BIN" install requests
fi

# Create instance directory if it doesn't exist
mkdir -p instance

# Set environment variables for production
export FLASK_APP=wsgi.py
export FLASK_ENV=production

# Start the application using gunicorn for production.
# Single worker: Flask-SocketIO long-polling is stateful and broadcasts don't
# cross processes without a message queue (SOCKETIO_MESSAGE_QUEUE). Threads
# provide the concurrency. --max-requests is intentionally absent: recycling
# the only worker would drop every live Socket.IO connection.
echo "Starting ClassPulse application..."
# --threads caps concurrent Socket.IO connections (one per connected audience
# page in threading async mode), so it caps class size. See the Dockerfile.
exec "$VENV_DIR/bin/gunicorn" \
    --bind 0.0.0.0:5000 \
    --workers 1 \
    --worker-class gthread \
    --threads "${GUNICORN_THREADS:-64}" \
    --timeout 60 \
    --keep-alive 2 \
    wsgi:application
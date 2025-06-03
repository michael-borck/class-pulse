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
    "$PIP_BIN" install requests cryptography
fi

# Create instance directory if it doesn't exist
mkdir -p instance

# Set environment variables for production
export FLASK_APP=app.py
export FLASK_ENV=production

# Start the application using gunicorn for production
echo "Starting ClassPulse application..."
exec "$VENV_DIR/bin/gunicorn" \
    --bind 0.0.0.0:5000 \
    --workers 4 \
    --worker-class gthread \
    --threads 2 \
    --timeout 30 \
    --keep-alive 2 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    app:app
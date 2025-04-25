#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Install MkDocs and required packages
pip install -r requirements.txt

# Build the documentation
echo "Building MkDocs site..."
mkdocs build

# Serve the documentation locally
echo "Starting local server at http://localhost:8000"
echo "Press Ctrl+C to stop the server"
mkdocs serve

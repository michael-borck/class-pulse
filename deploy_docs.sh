#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Install MkDocs and required packages if not already installed
pip install -r requirements.txt

# Build the site for GitHub Pages
echo "Building site for GitHub Pages deployment..."
mkdocs gh-deploy --force

echo "Deployment complete!"
echo "Your documentation should be available at: https://yourusername.github.io/classpulse/"
echo "Note: Replace 'yourusername' with your actual GitHub username in the URL."

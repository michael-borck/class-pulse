# ClassPulse Documentation

This directory contains the documentation for the ClassPulse project, formatted for MkDocs with the Material theme.

## Documentation Structure

- `index.md`: Home page
- `GETTING_STARTED.md`: Installation and basic usage guide
- `ARCHITECTURE.md`: System architecture and components
- `SPECIFICATION.md`: Detailed requirements and specifications
- `DEVELOPER_GUIDE.md`: Guide for developers working with the codebase
- `DATA_FLOW.md`: Visual representation of data flows through the system
- `API_REFERENCE.md`: Complete reference of all APIs and functions
- `assets/`: Directory for images and other assets

## Running Locally

To view the documentation locally:

1. Make sure you have activated the virtual environment:
   ```bash
   source venv/bin/activate
   ```

2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the MkDocs development server:
   ```bash
   mkdocs serve
   ```

4. Open your browser and go to http://localhost:8000

Alternatively, use the provided script:
```bash
./setup_docs.sh
```

## Deploying to GitHub Pages

To deploy the documentation to GitHub Pages:

1. Run the deployment script:
   ```bash
   ./deploy_docs.sh
   ```

2. Your documentation will be available at:
   https://yourusername.github.io/classpulse/

   (Replace 'yourusername' with your actual GitHub username)

## Updating the Documentation

1. Edit the Markdown files in the `docs/` directory
2. Preview your changes using `mkdocs serve`
3. Commit your changes
4. Deploy using `mkdocs gh-deploy` or the provided script

## MkDocs Configuration

The MkDocs configuration is in the `mkdocs.yml` file in the project root. You can customize:

- Navigation structure
- Theme and colors
- Plugins
- Extensions
- And more

For more information, see the [MkDocs documentation](https://www.mkdocs.org/) and 
[Material for MkDocs documentation](https://squidfunk.github.io/mkdocs-material/).

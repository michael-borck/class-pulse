.PHONY: setup setup-prod format lint type-check test coverage clean run dev prod docker-build docker-up docker-down help

# Variables
PYTHON = python3
APP_NAME = classpulse
PORT = 5002
WSGI_PORT = 8000

help:
	@echo "Available commands:"
	@echo "  setup         Install dependencies and set up development environment"
	@echo "  setup-prod    Install production dependencies"
	@echo "  format        Format code with ruff"
	@echo "  lint          Run linter (ruff)"
	@echo "  type-check    Run type checking with mypy"
	@echo "  test          Run tests with pytest"
	@echo "  coverage      Run tests with coverage report"
	@echo "  clean         Remove Python compiled files, test cache, coverage reports"
	@echo "  run           Run development server"
	@echo "  dev           Format, lint, type-check, and test"
	@echo "  prod          Run gunicorn WSGI server (production)"
	@echo "  docker-build  Build Docker image"
	@echo "  docker-up     Start application with Docker Compose"
	@echo "  docker-down   Stop Docker Compose services"
	@echo "  db-init       Initialize the database"
	@echo "  db-upgrade    Upgrade database using flask-migrate (if implemented)"

setup:
	uv pip install -e ".[dev]"
	@echo "Creating instance directory..."
	mkdir -p instance

setup-prod:
	uv pip install -e ".[prod]"
	@echo "Creating instance directory..."
	mkdir -p instance

format:
	ruff format .

lint:
	ruff check .

type-check:
	mypy .

test:
	pytest tests/

coverage:
	pytest --cov=$(APP_NAME) --cov-report=term --cov-report=html

clean:
	@echo "Removing Python cache files..."
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +

run:
	$(PYTHON) app.py

db-init:
	$(PYTHON) -c "from app import app, db; app.app_context().push(); db.create_all()"

db-upgrade:
	flask db upgrade

dev: format lint type-check test

prod:
	gunicorn --workers=3 --bind=0.0.0.0:$(WSGI_PORT) --worker-class=eventlet 'wsgi:application'

docker-build:
	docker build -t classpulse:latest .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down
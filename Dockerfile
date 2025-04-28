FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -e ".[prod]"

# Create necessary directories
RUN mkdir -p /app/instance /app/logs

# Expose the port for Gunicorn
EXPOSE 8000

# Run Gunicorn with Eventlet workers
CMD ["gunicorn", "--workers=3", "--bind=0.0.0.0:8000", "--worker-class=eventlet", "wsgi:application"]
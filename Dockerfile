FROM python:3.11-slim

WORKDIR /app

# App version (passed by CI as the git commit SHA; defaults to "dev").
ARG APP_VERSION=dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_VERSION=$APP_VERSION

# Copy requirements first for better caching. All dependencies ship wheels for
# python:3.11-slim, so no compiler toolchain is needed in the image.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Run as a non-root user. UID/GID 1000 so a bind-mounted ./instance owned by
# the first host user is writable; for other owners run:
#   sudo chown -R 1000:1000 instance logs
RUN groupadd -g 1000 app && useradd -m -u 1000 -g app app \
    && mkdir -p /app/instance /app/logs \
    && chown -R app:app /app
USER app

# Expose the port for Gunicorn
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=3).status == 200 else 1)"]

# Single worker: Flask-SocketIO long-polling is stateful and broadcasts don't
# cross processes without a message queue. Threads provide the concurrency.
# To scale out instead, set SOCKETIO_MESSAGE_QUEUE (Redis) and raise --workers.
#
# In threading async mode each connected audience page occupies a thread for
# the life of its Socket.IO connection, so --threads is effectively the cap on
# concurrent students. At 16 a normal class queued behind live connections and
# the whole app felt slow. Threads are cheap here (idle, I/O-bound, ~100 KB
# resident each), so 64 costs little. Raise GUNICORN_THREADS for a big lecture
# without rebuilding; past a few hundred, move to a gevent worker instead.
CMD ["sh", "-c", "exec gunicorn --workers=1 --bind=0.0.0.0:5000 --worker-class=gthread --threads=${GUNICORN_THREADS:-64} --timeout=60 wsgi:application"]

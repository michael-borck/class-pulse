"""
WSGI entry point for ClassPulse application.
This file enables running the application with production WSGI servers like Gunicorn.
"""

import os
from app import app, db

# Note: SECRET_KEY / DATABASE_URL are already read from the environment in
# app.py, so no override is needed here.

# Check the environment variable FLASK_ENV to determine if we're in debug mode
debug = os.environ.get('FLASK_ENV') == 'development'

# Optional: setup logging
if not debug:
    import logging
    from logging.handlers import RotatingFileHandler
    
    # Ensure log directory exists
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    file_handler = RotatingFileHandler('logs/classpulse.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('ClassPulse startup')

# Initialize the schema on startup. The __main__ block in app.py only runs
# under `python app.py`, so production (gunicorn) relies on this.
# Admin bootstrapping is handled by the register flow: the first person to
# register becomes a verified admin — no default admin account is created.
with app.app_context():
    db.create_all()

# This will be used by Gunicorn. For Flask-SocketIO the WSGI callable is the
# Flask app itself — SocketIO installs middleware that handles /socket.io/.
# (For true websockets, run gunicorn with an eventlet/gevent worker class;
# with sync/gthread workers Socket.IO falls back to HTTP long-polling.)
application = app
"""
WSGI entry point for ClassPulse.
This file enables running the application with production WSGI servers like Gunicorn.

The factory initializes the schema (create_all) and reads all configuration
from the environment / .env — see .env.example.

For Flask-SocketIO the WSGI callable is the Flask app itself — SocketIO
installs middleware that handles /socket.io/. With the default sync/gthread
workers Socket.IO uses HTTP long-polling; run a single worker process unless
SOCKETIO_MESSAGE_QUEUE points at a shared queue (e.g. Redis), because
broadcasts do not cross process boundaries without one.
"""

import os

from classpulse import create_app

debug = os.environ.get('FLASK_ENV') == 'development'

application = create_app()

if not debug:
    import logging
    from logging.handlers import RotatingFileHandler

    if not os.path.exists('logs'):
        os.mkdir('logs')

    file_handler = RotatingFileHandler('logs/classpulse.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    application.logger.addHandler(file_handler)
    application.logger.setLevel(logging.INFO)
    application.logger.info('ClassPulse startup')

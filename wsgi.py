"""
WSGI entry point for ClassPulse application.
This file enables running the application with production WSGI servers like Gunicorn.
"""

import os
from app import app, socketio

# Override configurations with environment variables if present
if os.environ.get('SECRET_KEY'):
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

if os.environ.get('DATABASE_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')

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

# This will be used by Gunicorn
application = socketio.WSGIApp(app)
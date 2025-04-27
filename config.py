# config.py

import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-classpulse'
    # Use absolute path for SQLite database
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(basedir, "instance", "classpulse.sqlite")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Default admin credentials (for demo purposes)
    ADMIN_USERNAME = 'admin'
    ADMIN_PASSWORD = 'password'
    
    # Socket.IO settings
    SOCKETIO_CORS_ALLOWED_ORIGINS = "*"


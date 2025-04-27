# extensions.py
# This file contains all the extensions used in the app
# to avoid circular imports

from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

# Initialize extensions
db = SQLAlchemy()
socketio = SocketIO(cors_allowed_origins="*")
# Shared Flask extension instances, created unbound and initialised in
# create_app(). Keeping them here avoids circular imports between the
# factory and the route/socket modules.

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
csrf = CSRFProtect()
socketio = SocketIO()
limiter = Limiter(get_remote_address, default_limits=[])

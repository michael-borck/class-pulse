# Development entry point: `python app.py` runs the Socket.IO dev server.
# Production uses wsgi.py (gunicorn). The application itself lives in the
# classpulse/ package.

import os

from classpulse import create_app
from classpulse.extensions import db, socketio  # noqa: F401  (db re-exported for shell use)

app = create_app()

if __name__ == '__main__':
    # Debug is OFF unless explicitly enabled, because the Werkzeug debugger
    # exposes an interactive console (remote code execution) and full source
    # tracebacks. Enable only for local development via FLASK_ENV=development
    # or DEBUG=true.
    debug_mode = (
        os.environ.get('FLASK_ENV') == 'development'
        or os.environ.get('DEBUG', '').lower() in ('1', 'true', 'yes')
    )
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5002))

    print(f"Starting Flask-SocketIO server on http://{host}:{port} (debug={debug_mode})")
    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug_mode,
        use_reloader=debug_mode,
        allow_unsafe_werkzeug=True,
    )

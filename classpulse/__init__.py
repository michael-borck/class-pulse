"""ClassPulse application factory.

Configuration is environment-driven (12-factor); see .env.example for every
supported variable. Entry points:
  - wsgi.py  -> create_app() for gunicorn (production)
  - app.py   -> create_app() + socketio.run() for `python app.py` (development)
"""

import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, g, jsonify, session
from werkzeug.middleware.proxy_fix import ProxyFix

from .extensions import csrf, db, limiter, socketio

APP_VERSION = os.environ.get("APP_VERSION") or "dev"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes')


def create_app(test_config: dict = None) -> Flask:
    # Load .env so the variables documented in .env.example take effect
    # (no-op when the file is missing).
    load_dotenv()

    app = Flask(
        'classpulse',
        template_folder=str(_PROJECT_ROOT / 'templates'),
        static_folder=str(_PROJECT_ROOT / 'static'),
        instance_path=str(_PROJECT_ROOT / 'instance'),
    )
    os.makedirs(app.instance_path, exist_ok=True)

    # SECRET_KEY signs the session cookie (which stores user_id), so a known or
    # shared key lets anyone forge a session and impersonate any user/admin. It
    # MUST come from the environment in production. If unset, we fall back to an
    # ephemeral random key so local/dev runs still work — but that key does not
    # survive a restart, so logins break. We warn loudly below.
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
    secret_key_is_ephemeral = not app.config['SECRET_KEY']
    if secret_key_is_ephemeral:
        app.config['SECRET_KEY'] = secrets.token_hex(32)

    app.config['SQLALCHEMY_DATABASE_URI'] = (
        os.environ.get('DATABASE_URL') or 'sqlite:///classpulse_flask.db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Session cookie hardening. Secure is opt-in via env so local HTTP dev still
    # works; set SESSION_COOKIE_SECURE=true when serving over HTTPS.
    cookie_secure = _env_bool('SESSION_COOKIE_SECURE')
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = cookie_secure
    # Login sets session.permanent, so authenticated sessions expire after this
    # many seconds rather than living as long as the browser process.
    app.config['PERMANENT_SESSION_LIFETIME'] = int(
        os.environ.get('PERMANENT_SESSION_LIFETIME', 86400))

    # Reject oversized request bodies outright (413). The largest legitimate
    # payload is a question form; 256 KB leaves generous headroom.
    app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 262144))

    # CSRF tokens have no time limit so long-lived presentation/audience pages
    # don't fail mid-session on submit.
    app.config['WTF_CSRF_TIME_LIMIT'] = None

    # Default in-memory store: adequate for the single-process deployment.
    # Set RATELIMIT_STORAGE_URI (e.g. redis://...) if you scale out.
    app.config.setdefault('RATELIMIT_STORAGE_URI',
                          os.environ.get('RATELIMIT_STORAGE_URI', 'memory://'))

    if test_config:
        app.config.update(test_config)

    # Behind a reverse proxy (Caddy/nginx), trust X-Forwarded-* from that many
    # hops so rate limits key on the real client IP and generated URLs use the
    # public scheme/host. TRUST_PROXY=0 (default) for direct exposure.
    trust_proxy = int(os.environ.get('TRUST_PROXY', '0') or 0)
    if trust_proxy > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=trust_proxy, x_proto=trust_proxy,
                                x_host=trust_proxy, x_port=trust_proxy)

    if secret_key_is_ephemeral and not app.config.get('TESTING'):
        app.logger.warning(
            "SECRET_KEY is not set; generated a temporary key. Sessions will not "
            "survive restarts. Set SECRET_KEY in the environment (or .env) for any "
            "non-trivial deployment."
        )

    # --- Extensions ---
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    # Import sockets BEFORE socketio.init_app: handlers registered before the
    # server exists land in SocketIO's deferred list and are re-attached on
    # every init_app; handlers registered after would be lost if create_app
    # runs more than once (as it does in tests).
    from . import sockets  # noqa: F401
    # For multi-process deployments set SOCKETIO_MESSAGE_QUEUE (e.g. redis://...)
    # so broadcasts reach clients connected to other workers. The default
    # deployment is single-process (see Dockerfile), which needs neither.
    socketio.init_app(
        app,
        async_mode=os.environ.get('SOCKETIO_ASYNC_MODE') or None,
        message_queue=os.environ.get('SOCKETIO_MESSAGE_QUEUE') or None,
    )

    # --- AI availability (module-level config; imported for the flag) ---
    from . import ai
    if ai.AI_ENABLED:
        app.logger.info(
            f"AI question generation enabled: provider={ai.AI_PROVIDER} model={ai.AI_MODEL}")
    elif ai.AI_PROVIDER or ai.AI_BASE_URL or ai.AI_MODEL:
        app.logger.warning(
            "AI is partially configured but disabled. Set AI_PROVIDER to 'openai' or "
            "'anthropic', plus AI_BASE_URL and AI_MODEL (see .env.example)."
        )

    # --- Jinja filters & context ---
    from .utils import format_datetime_filter, fromjson_filter
    app.jinja_env.filters['format_datetime'] = format_datetime_filter
    app.jinja_env.filters['fromjson'] = fromjson_filter

    @app.context_processor
    def inject_now():
        return {'now': lambda: datetime.now(timezone.utc), 'app_version': APP_VERSION}

    @app.context_processor
    def inject_user_and_admin_status():
        from .models import User
        user = None
        is_admin = False
        if 'user_id' in session:
            if 'user' not in g or g.user is None:
                g.user = db.session.get(User, session['user_id'])
            user = g.user
            if user:
                is_admin = user.is_admin
        return {'current_user': user, 'is_admin': is_admin, 'ai_enabled': ai.AI_ENABLED}

    # --- Security headers ---
    csp = os.environ.get(
        'CONTENT_SECURITY_POLICY',
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' ws: wss:; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; "
        "frame-ancestors 'self'"
    )

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        if csp:
            response.headers.setdefault('Content-Security-Policy', csp)
        if cookie_secure:
            response.headers.setdefault('Strict-Transport-Security',
                                        'max-age=31536000; includeSubDomains')
        return response

    # --- Health check (for Docker HEALTHCHECK / uptime monitors) ---
    @app.route('/healthz')
    @limiter.exempt
    def healthz():
        return jsonify({"status": "ok", "version": APP_VERSION})

    # --- Routes ---
    from . import admin, audience, auth, presenter
    auth.init_app(app)
    presenter.init_app(app)
    audience.init_app(app)
    admin.init_app(app)

    # --- Schema ---
    # create_all() creates missing tables only; it never alters existing ones.
    if app.config.get('AUTO_CREATE_TABLES', True):
        with app.app_context():
            try:
                db.create_all()
            except Exception as e:
                # Multiple processes booting against a fresh DB can race the
                # check-then-create inside create_all() ("table already exists").
                # The first to win creates every table; the rest hit this benign
                # error and continue.
                if "already exists" not in str(e):
                    raise

    return app

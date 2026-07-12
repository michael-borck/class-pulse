"""Password handling, auth decorators, and the login/logout/register routes."""

import hashlib
import hmac
import re
import threading
from functools import wraps

from flask import flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, limiter
from .models import User

# Explicit method (rather than werkzeug's default scrypt) so the hash string
# stays under the column length on every backend, and so the work factor is
# pinned at the OWASP-recommended iteration count.
PASSWORD_HASH_METHOD = "pbkdf2:sha256:600000"

# Verified against when a login names an unknown user, so response timing does
# not reveal whether a username exists.
_DUMMY_HASH = generate_password_hash("classpulse-timing-equalizer", method=PASSWORD_HASH_METHOD)

# Guards the "first registered user becomes admin" check-then-insert so two
# concurrent registrations on a fresh DB can't both become admin. A process
# lock is sufficient: the app runs single-process (see Dockerfile/start.sh).
_FIRST_ADMIN_LOCK = threading.Lock()


def hash_password(password: str) -> str:
    return generate_password_hash(password, method=PASSWORD_HASH_METHOD)


def verify_password(stored_password_hash: str, provided_password: str) -> bool:
    """Verify against the current werkzeug format or the legacy salt$hash format."""
    if stored_password_hash.startswith(("pbkdf2:", "scrypt:")):
        return check_password_hash(stored_password_hash, provided_password)
    # Legacy format from earlier releases: "<salt hex>$<pbkdf2-sha256(100k) hex>"
    try:
        salt_hex, hash_hex = stored_password_hash.split('$', 1)
        salt = bytes.fromhex(salt_hex)
        stored_hash = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    provided_hash = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
    return hmac.compare_digest(stored_hash, provided_hash)


def password_needs_rehash(stored_password_hash: str) -> bool:
    return not stored_password_hash.startswith(PASSWORD_HASH_METHOD + "$")


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        g.user = db.session.get(User, session['user_id'])
        if not g.user:
            session.clear()
            flash("Invalid session. Please log in again.", "warning")
            return redirect(url_for('login'))
        if g.user.is_archived and request.endpoint != 'logout':
            session.clear()
            flash("Your account has been archived. Please contact an administrator.", "danger")
            return redirect(url_for('login'))
        # Unverified users may only log out; admins pass through so they can
        # verify others even if their own flag is somehow unset.
        if not g.user.is_verified and request.endpoint != 'logout' and not g.user.is_admin:
            session.clear()
            flash("Your account is not verified. Please contact an administrator.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not g.user or not g.user.is_admin:
            flash("You do not have permission to access this page.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def init_app(app):

    @app.route('/login', methods=['GET', 'POST'])
    @limiter.limit("10 per minute", methods=["POST"])
    def login():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password') or ''
            user = User.query.filter_by(username=username).first()

            if not user:
                # Equalize timing with the real-user path.
                check_password_hash(_DUMMY_HASH, password)
                flash("Invalid username or password.", "danger")
                return render_template('login.html', username=username)

            if not verify_password(user.password_hash, password):
                flash("Invalid username or password.", "danger")
                return render_template('login.html', username=username)

            if user.is_archived:
                flash("Your account has been archived. Please contact an administrator.", "danger")
                return render_template('login.html', username=username)
            if not user.is_verified and not user.is_admin:
                flash("Your account is not verified. Please contact an administrator.", "warning")
                return render_template('login.html', username=username)

            # Transparently upgrade legacy hashes now that we have the plaintext.
            if password_needs_rehash(user.password_hash):
                user.password_hash = hash_password(password)
                db.session.commit()

            session.permanent = True  # honour PERMANENT_SESSION_LIFETIME
            session['user_id'] = user.id
            session['display_name'] = user.display_name or user.username
            flash(f"Welcome back, {session['display_name']}!", "success")
            return redirect(url_for('dashboard'))

        return render_template('login.html')

    @app.route('/logout', methods=['POST'])
    @login_required
    def logout():
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for('login'))

    @app.route('/register', methods=['GET', 'POST'])
    @limiter.limit("20 per hour", methods=["POST"])
    def register():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            username = (request.form.get('username') or '').strip()
            email = (request.form.get('email') or '').strip()
            display_name = (request.form.get('display_name') or '').strip() or username
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            errors = []
            if not username:
                errors.append("Username is required.")
            if not email:
                errors.append("Email is required.")
            if not password:
                errors.append("Password is required.")
            if len(password or "") < 10:
                errors.append("Password must be at least 10 characters long.")
            if password != confirm_password:
                errors.append("Passwords do not match.")
            if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                errors.append("Invalid email address.")
            if username and User.query.filter_by(username=username).first():
                errors.append("Username already taken.")
            if email and User.query.filter_by(email=email).first():
                errors.append("Email address already registered.")

            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template('register.html', username=username, email=email,
                                       display_name=display_name)

            # The first user on a fresh deployment becomes a verified admin
            # automatically, so the app is usable without log-grepping.
            try:
                with _FIRST_ADMIN_LOCK:
                    is_first_admin = (User.query.filter_by(is_admin=True).count() == 0)
                    new_user = User(
                        username=username,
                        email=email,
                        password_hash=hash_password(password),
                        display_name=display_name,
                        is_admin=is_first_admin,
                        is_verified=is_first_admin,  # the bootstrap admin is auto-verified
                        is_archived=False,
                    )
                    db.session.add(new_user)
                    db.session.commit()
            except Exception:
                db.session.rollback()
                app.logger.exception("Error during registration commit")
                flash("An error occurred during registration. Please try again.", "danger")
                return render_template('register.html', username=username, email=email,
                                       display_name=display_name)

            if is_first_admin:
                flash("Registration successful! You're the first user, so your account is "
                      "the admin — you can log in now.", "success")
                app.logger.info(f"First user '{username}' registered as the bootstrap admin.")
            else:
                flash("Registration successful! Your account requires verification by an "
                      "administrator before you can log in.", "success")
            return redirect(url_for('login'))

        return render_template('register.html')

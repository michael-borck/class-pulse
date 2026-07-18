"""Password handling, auth decorators, and the login/logout/register routes.

Registration is email-verified: a new user receives a single-use code and can't
log in until they confirm it (see the email/verify/reset routes below). A
forgotten password is recovered the same way. Email delivery is pluggable — see
email.py; the default 'dev' provider just logs the code.
"""

import hashlib
import hmac
import re
import secrets
import string
import threading
from functools import wraps

from flask import (
    current_app, flash, g, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .accounts import is_last_admin, purge_user
from .email import provider_name as email_provider_name
from .email import send_password_reset_email, send_verification_email
from .extensions import db, limiter
from .models import (
    EMAIL_CODE_RESET, EMAIL_CODE_VERIFY, EmailCode, User, new_session_token,
)

# Codes are short, single-use, rate-limited and user-scoped, so an 8-char
# alphanumeric space (~2.8e12) is ample.
_CODE_CHARSET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 8


def _generate_code() -> str:
    return "".join(secrets.choice(_CODE_CHARSET) for _ in range(_CODE_LENGTH))


def _issue_email_code(user: User, purpose: str) -> str:
    """Persist a fresh code for `purpose`, retiring any prior unused ones, and
    return it. Retiring older codes means only the newest email works."""
    ttl = current_app.config['EMAIL_CODE_TTL_MIN']
    EmailCode.query.filter_by(user_id=user.id, purpose=purpose, used=False).update(
        {'used': True})
    code = _generate_code()
    db.session.add(EmailCode(user_id=user.id, code=code, purpose=purpose,
                             expires_at=EmailCode.expiry_iso(ttl)))
    db.session.commit()
    return code


def _consume_email_code(user: User, purpose: str, code: str) -> bool:
    """Mark a matching valid code used and return True; else False."""
    normalized = (code or '').strip().upper()
    if not normalized:
        return False
    record = (EmailCode.query
              .filter_by(user_id=user.id, purpose=purpose, code=normalized, used=False)
              .order_by(EmailCode.id.desc()).first())
    if record is None or not record.is_valid:
        return False
    record.used = True
    db.session.commit()
    return True


def _ensure_session_token(user: User) -> None:
    """Give the user a session token if they lack one (backfill/first login)."""
    if not user.session_token:
        user.session_token = new_session_token()
        db.session.commit()

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
            flash("Your account has been blocked. Please contact an administrator.", "danger")
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
                flash("Your account has been blocked. Please contact an administrator.", "danger")
                return render_template('login.html', username=username)
            if not user.is_verified and not user.is_admin:
                flash("Your email is not verified. Enter the code we emailed you, "
                      "or request a new one.", "warning")
                return render_template('login.html', username=username,
                                       show_verify_link=True, verify_email=user.email)

            # Transparently upgrade legacy hashes now that we have the plaintext.
            if password_needs_rehash(user.password_hash):
                user.password_hash = hash_password(password)
                db.session.commit()

            _ensure_session_token(user)
            session.permanent = True  # honour PERMANENT_SESSION_LIFETIME
            session['user_id'] = user.id
            session['session_token'] = user.session_token
            session['display_name'] = user.display_name or user.username
            flash(f"Welcome back, {session['display_name']}!", "success")
            return redirect(url_for('dashboard'))

        return render_template('login.html')

    @app.route('/logout', methods=['POST'])
    @login_required
    def logout():
        session.clear()
        # Land on the public page rather than the login form: signing out is not
        # a prompt to sign back in. No flash — the landing template renders no
        # flash block, so a queued message would surface on some later page.
        return redirect(url_for('index'))

    @app.route('/account')
    @login_required
    def account():
        return render_template('account.html', user=g.user)

    @app.route('/account/delete', methods=['POST'])
    @login_required
    @limiter.limit("10 per hour")
    def account_delete():
        # Deleting is irreversible and takes every session/response with it, so
        # require the current password — a walked-away session shouldn't be able
        # to nuke the account with one click.
        password = request.form.get('password') or ''
        if not verify_password(g.user.password_hash, password):
            flash("That password is incorrect. Your account was not deleted.", "danger")
            return redirect(url_for('account'))
        # Refuse if this is the last admin: an adminless deployment auto-promotes
        # the next registrant, so make them hand over admin first.
        if is_last_admin(g.user):
            flash("You're the only administrator. Make another user an admin "
                  "before deleting your account.", "danger")
            return redirect(url_for('account'))
        purge_user(g.user)
        session.clear()
        # Lands on the public landing page (which renders no flash, so none is set).
        return redirect(url_for('index'))

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

            allowed_domains = app.config.get('ALLOWED_DOMAINS') or []

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
            if email and allowed_domains and email.rsplit('@', 1)[-1].lower() not in allowed_domains:
                errors.append("Registration is restricted to these email domains: "
                              + ", ".join(allowed_domains) + ".")
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
            # automatically, so the app is usable without log-grepping. Everyone
            # else must confirm their email before they can log in.
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
                return redirect(url_for('login'))

            # Email a verification code and send them to the verify page. If the
            # provider failed, say so — telling someone to check an inbox that
            # will never receive anything just strands them.
            code = _issue_email_code(new_user, EMAIL_CODE_VERIFY)
            sent = send_verification_email(new_user.email,
                                           new_user.display_name or new_user.username,
                                           code, app.config['EMAIL_CODE_TTL_MIN'])
            if sent:
                flash("Registration successful! Check your email for a verification code "
                      "to activate your account.", "success")
            else:
                app.logger.error("Verification email could not be sent to %s during "
                                 "registration (EMAIL_PROVIDER=%s).",
                                 new_user.email, email_provider_name())
                flash("Your account was created, but we couldn't send the verification "
                      "email. Ask your administrator to check the email configuration, "
                      "then request a new code below.", "danger")
            return redirect(url_for('verify_email', email=new_user.email))

        return render_template('register.html')

    # Generic response for email-keyed flows so the presence or absence of an
    # account is never revealed (no account enumeration).
    _GENERIC_EMAIL_SENT = ("If an account with that email exists, we've sent it a "
                           "code. Check your inbox.")

    @app.route('/verify-email', methods=['GET', 'POST'])
    @limiter.limit("10 per minute", methods=["POST"])
    def verify_email():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            email = (request.form.get('email') or '').strip()
            code = request.form.get('code') or ''
            user = User.query.filter_by(email=email).first()

            if user and not user.is_verified and _consume_email_code(user, EMAIL_CODE_VERIFY, code):
                user.is_verified = True
                db.session.commit()
                app.logger.info(f"User '{user.username}' verified their email.")
                flash("Email verified! You can now log in.", "success")
                return redirect(url_for('login'))

            # Same message whether the user, code, or verified-state was wrong,
            # so nothing is leaked about which accounts exist.
            flash("That code is invalid or has expired. Request a new one below.", "danger")
            return render_template('verify_email.html', email=email)

        return render_template('verify_email.html', email=request.args.get('email', ''))

    @app.route('/resend-verification', methods=['POST'])
    @limiter.limit("5 per hour")
    def resend_verification():
        email = (request.form.get('email') or '').strip()
        user = User.query.filter_by(email=email).first()
        # Only unverified accounts get a fresh code; response is always generic.
        if user and not user.is_verified:
            code = _issue_email_code(user, EMAIL_CODE_VERIFY)
            if not send_verification_email(user.email, user.display_name or user.username,
                                           code, app.config['EMAIL_CODE_TTL_MIN']):
                # Deliberately not surfaced: a delivery-failure message here would
                # only appear for addresses that have an account, which is exactly
                # the account enumeration the generic response exists to prevent.
                app.logger.error("Verification email could not be resent to %s "
                                 "(EMAIL_PROVIDER=%s).", user.email, email_provider_name())
        flash(_GENERIC_EMAIL_SENT, "info")
        return redirect(url_for('verify_email', email=email))

    @app.route('/forgot-password', methods=['GET', 'POST'])
    @limiter.limit("5 per hour", methods=["POST"])
    def forgot_password():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            email = (request.form.get('email') or '').strip()
            user = User.query.filter_by(email=email).first()
            # Don't send reset codes to archived accounts, but never reveal it.
            if user and not user.is_archived:
                code = _issue_email_code(user, EMAIL_CODE_RESET)
                if not send_password_reset_email(user.email,
                                                 user.display_name or user.username,
                                                 code, app.config['EMAIL_CODE_TTL_MIN']):
                    # Logged, not flashed — see resend_verification for why.
                    app.logger.error("Password reset email could not be sent to %s "
                                     "(EMAIL_PROVIDER=%s).", user.email,
                                     email_provider_name())
            flash(_GENERIC_EMAIL_SENT, "info")
            return redirect(url_for('reset_password', email=email))

        return render_template('forgot_password.html')

    @app.route('/reset-password', methods=['GET', 'POST'])
    @limiter.limit("10 per minute", methods=["POST"])
    def reset_password():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            email = (request.form.get('email') or '').strip()
            code = request.form.get('code') or ''
            password = request.form.get('password') or ''
            confirm_password = request.form.get('confirm_password') or ''

            errors = []
            if len(password) < 10:
                errors.append("Password must be at least 10 characters long.")
            if password != confirm_password:
                errors.append("Passwords do not match.")
            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template('reset_password.html', email=email)

            user = User.query.filter_by(email=email).first()
            if not user or not _consume_email_code(user, EMAIL_CODE_RESET, code):
                flash("That code is invalid or has expired. Request a new one.", "danger")
                return render_template('reset_password.html', email=email)

            user.password_hash = hash_password(password)
            # Rotate the session token so any existing logins (other devices)
            # are invalidated, and mark the email verified — controlling the
            # inbox is at least as strong as the verification step.
            user.session_token = new_session_token()
            user.is_verified = True
            db.session.commit()
            app.logger.info(f"User '{user.username}' reset their password.")
            flash("Password reset! Log in with your new password.", "success")
            return redirect(url_for('login'))

        return render_template('reset_password.html', email=request.args.get('email', ''))

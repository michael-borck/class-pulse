# Main application entry point for ClassPulse (Flask Version)

# --- Imports ---
import os
import uuid
import json
import hashlib
import secrets
import io
import csv
from datetime import datetime # Added datetime import
from typing import List, Dict, Optional, Tuple, Any
from functools import wraps
import re # For email validation

# Flask and Extensions
from flask import (
    Flask, render_template, request, redirect, url_for, session,
    flash, make_response, jsonify, abort, send_file, g # Added g for admin check
)
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room

# External Libraries (Ensure these are installed)
import qrcode as qr_code_lib
from PIL import Image
import base64

# --- Flask App Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32) # Replace with env var in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///classpulse_flask.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Database Setup (using Flask-SQLAlchemy) ---
db = SQLAlchemy(app)
# Use eventlet or gevent for production async mode
# For development, the default Flask development server works but might be less performant for WebSockets
socketio = SocketIO(app, async_mode=None) # Changed async_mode for broader compatibility in dev

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    display_name = db.Column(db.String(100))
    is_admin = db.Column(db.Boolean, default=False, nullable=False) # New: Admin flag
    is_verified = db.Column(db.Boolean, default=False, nullable=False) # New: Verification flag
    is_archived = db.Column(db.Boolean, default=False, nullable=False) # New: Archive flag
    sessions = db.relationship('Session', backref='creator', lazy=True)

class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.String, default=lambda: datetime.now().isoformat())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    archived = db.Column(db.Boolean, default=False, nullable=False) # New field for archiving
    questions = db.relationship('Question', backref='session', lazy=True, order_by='Question.order, Question.created_at')
    responses = db.relationship('Response', backref='session', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False) # 'multiple_choice', 'word_cloud', 'rating'
    title = db.Column(db.String(255), nullable=False)
    options = db.Column(db.Text, default='{}') # JSON string for options/config
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.String, default=lambda: datetime.now().isoformat())
    order = db.Column(db.Integer, default=0)
    responses = db.relationship('Response', backref='question', lazy=True)

class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)
    response_value = db.Column(db.Text, nullable=False)
    respondent_id = db.Column(db.String(36), nullable=False) # Anonymous UUID
    created_at = db.Column(db.String, default=lambda: datetime.now().isoformat())

# --- Constants & Config ---
DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASS = "admin123" # Change this!
RESPONDENT_COOKIE_NAME = "classpulse_respondent"

# Basic English stop words list (can be expanded)
STOP_WORDS = set([
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't", "as", "at",
    "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd",
    "he'll", "he's", "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself",
    "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out",
    "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these", "they",
    "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too", "under", "until", "up", "very",
    "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's",
    "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't",
    "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
])


# --- Context Processors ---
@app.context_processor
def inject_now():
    """Injects the current UTC datetime into the template context."""
    return {'now': datetime.utcnow} # Make datetime.utcnow available as 'now'

@app.context_processor
def inject_user_and_admin_status():
    """Injects the current user object and admin status into the template context."""
    user = None
    is_admin = False
    if 'user_id' in session:
        # Use g to cache user object per request if needed elsewhere
        # Check if g.user exists and is still valid (not None after query)
        if 'user' not in g or g.user is None:
            # Use Session.get() which is preferred in SQLAlchemy 2.0+
            g.user = db.session.get(User, session['user_id'])
        user = g.user
        if user:
            is_admin = user.is_admin
    return {'current_user': user, 'is_admin': is_admin}

# --- Utility Functions ---

# QR Code Generation
def create_qr_code_data(url: str, size: int = 200) -> Optional[str]:
    """Creates a QR code data URL for a given URL."""
    try:
        qr = qr_code_lib.QRCode(
            version=1,
            error_correction=qr_code_lib.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").resize((size, size))
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        print(f"Error generating QR code: {e}")
        return None

# Session Code Generation
def generate_session_code(length: int = 6) -> str:
    """Generates a random alphanumeric code, ensuring uniqueness."""
    while True:
        code = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(length))
        # Ensure the query is executed within an application context if run outside a request
        with app.app_context():
            existing = Session.query.filter_by(code=code).first()
        if not existing:
            return code

# Authentication Helpers
def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    """Hashes a password with PBKDF2 and salt."""
    if salt is None:
        salt = secrets.token_bytes(16)
    password_bytes = password.encode('utf-8')
    hashed = hashlib.pbkdf2_hmac('sha256', password_bytes, salt, 100000)
    return f"{salt.hex()}${hashed.hex()}"

def verify_password(stored_password_hash: str, provided_password: str) -> bool:
    """Verifies a password against a stored hash."""
    try:
        salt_hex, hash_hex = stored_password_hash.split('$', 1)
        salt = bytes.fromhex(salt_hex)
        stored_hash = bytes.fromhex(hash_hex)
        provided_password_bytes = provided_password.encode('utf-8')
        provided_hash = hashlib.pbkdf2_hmac('sha256', provided_password_bytes, salt, 100000)
        return secrets.compare_digest(stored_hash, provided_hash)
    except (ValueError, IndexError):
        return False

# Decorator for routes requiring login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Use Flask's session proxy directly
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        # Load user into g for potential use in the request context
        # Use Session.get() which is preferred in SQLAlchemy 2.0+
        g.user = db.session.get(User, session['user_id'])
        if not g.user: # Handle case where user_id in session is invalid
             session.clear()
             flash("Invalid session. Please log in again.", "warning")
             return redirect(url_for('login'))
        # Prevent archived users from accessing protected routes (except logout)
        if g.user.is_archived and request.endpoint != 'logout':
            session.clear()
            flash("Your account has been archived. Please contact an administrator.", "danger")
            return redirect(url_for('login'))
        # Prevent unverified users from accessing protected routes (except logout and admin pages)
        # Allow access to logout regardless of verification status
        # Allow access for admins to admin pages even if somehow unverified (shouldn't happen)
        allowed_endpoints = ['logout', 'admin_manage_users', 'api_toggle_verify_user', 'api_toggle_archive_user']
        if not g.user.is_verified and request.endpoint not in allowed_endpoints:
             # If the user is an admin, let them proceed (they might need to verify others)
             if not g.user.is_admin:
                session.clear() # Log them out if they somehow got a session
                flash("Your account is not verified. Please contact an administrator.", "warning")
                return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorator for admin-only routes
def admin_required(f):
    @wraps(f)
    @login_required # Ensure user is logged in first
    def decorated_function(*args, **kwargs):
        # g.user should be populated by @login_required
        if not g.user or not g.user.is_admin:
            flash("You do not have permission to access this page.", "danger")
            return redirect(url_for('dashboard')) # Redirect non-admins
        return f(*args, **kwargs)
    return decorated_function


# --- Custom Jinja Filters ---
def format_datetime_filter(value, format='%Y-%m-%d %H:%M'):
    """Formats an ISO datetime string."""
    if value is None:
        return ""
    try:
        # Handle potential timezone info if present (e.g., +00:00 or Z)
        dt_object = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt_object.strftime(format)
    except (ValueError, TypeError):
        return value # Return original if parsing fails

# Register the filter with Jinja environment
app.jinja_env.filters['format_datetime'] = format_datetime_filter

def fromjson_filter(value):
    """Loads JSON string into Python object."""
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
         # Return default based on expected type (list for MC, dict for rating)
         # This is a simplification; might need more context
         # Check if it looks like a list or dict string before returning default
        if isinstance(value, str):
            if value.strip().startswith('['): return []
            if value.strip().startswith('{'): return {}
        return {} # Default fallback

# Register the filter with Jinja environment
app.jinja_env.filters['fromjson'] = fromjson_filter


# --- Authentication Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session: # Use Flask session
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        # Check if user exists and password is correct
        if user and verify_password(user.password_hash, password):
            # Check if user is archived
            if user.is_archived:
                flash("Your account has been archived. Please contact an administrator.", "danger")
                return render_template('login.html', username=username)
            # FIX: Check if user is verified (unless they are admin)
            if not user.is_verified and not user.is_admin:
                flash("Your account is not verified. Please contact an administrator.", "warning")
                return render_template('login.html', username=username)

            # If all checks pass, log the user in
            session['user_id'] = user.id # Use Flask session
            session['display_name'] = user.display_name or user.username # Use Flask session
            flash(f"Welcome back, {session['display_name']}!", "success") # Use Flask session
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.", "danger")
            return render_template('login.html', username=username) # Pass back username

    return render_template('login.html')

@app.route('/logout')
@login_required # Keep login_required to ensure g.user might be set for logging, etc.
def logout():
    session.clear() # Use Flask session
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if 'user_id' in session:
        return redirect(url_for('dashboard')) # Redirect if already logged in

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        display_name = request.form.get('display_name') or username # Default display name to username
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # --- Validation ---
        errors = []
        if not username: errors.append("Username is required.")
        if not email: errors.append("Email is required.")
        if not password: errors.append("Password is required.")
        if len(password) < 6: errors.append("Password must be at least 6 characters long.") # Basic length check
        if password != confirm_password: errors.append("Passwords do not match.")
        # Basic email format check
        if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
             errors.append("Invalid email address.")
        # Check uniqueness
        if username and User.query.filter_by(username=username).first():
            errors.append("Username already taken.")
        if email and User.query.filter_by(email=email).first():
             errors.append("Email address already registered.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template('register.html', username=username, email=email, display_name=display_name)
        # --- End Validation ---

        # Create user (default: not admin, not verified, not archived)
        password_h = hash_password(password)
        new_user = User(
            username=username,
            email=email,
            password_hash=password_h,
            display_name=display_name,
            is_admin=False,
            is_verified=False, # Require admin verification
            is_archived=False
            )
        db.session.add(new_user)
        try:
            db.session.commit()
            flash("Registration successful! Your account requires verification by an administrator before you can log in.", "success") # Inform about verification
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            print(f"Error during registration commit: {e}")
            flash("An error occurred during registration. Please try again.", "danger")
            return render_template('register.html', username=username, email=email, display_name=display_name)

    # GET request
    return render_template('register.html')


# --- Presenter Routes ---
@app.route('/')
@login_required
def dashboard():
    user_id = session['user_id'] # Use Flask session
    # Filter out archived sessions
    user_sessions = Session.query.filter_by(user_id=user_id, archived=False).order_by(Session.created_at.desc()).all()
    active_sessions = [s for s in user_sessions if s.active]
    inactive_sessions = [s for s in user_sessions if not s.active]
    # Optionally, get archived sessions for a separate view/link
    # archived_sessions = Session.query.filter_by(user_id=user_id, archived=True).order_by(Session.created_at.desc()).all()
    return render_template('dashboard.html',
                           active_sessions=active_sessions,
                           inactive_sessions=inactive_sessions)
                           # archived_sessions=archived_sessions) # Pass archived if needed

@app.route('/sessions')
@login_required
def list_sessions():
    user_id = session['user_id'] # Use Flask session
    # Filter out archived sessions
    user_sessions = Session.query.filter_by(user_id=user_id, archived=False).order_by(Session.created_at.desc()).all()
    return render_template('sessions_list.html', sessions=user_sessions)

# Optional: Route to view archived sessions
@app.route('/sessions/archived')
@login_required
def list_archived_sessions():
    user_id = session['user_id']
    archived_sessions = Session.query.filter_by(user_id=user_id, archived=True).order_by(Session.created_at.desc()).all()
    return render_template('sessions_archived.html', sessions=archived_sessions) # Need to create this template


@app.route('/sessions/new', methods=['GET', 'POST'])
@login_required
def new_session():
    if request.method == 'POST':
        name = request.form.get('name')
        if not name:
            flash("Session name is required.", "danger")
            return render_template('session_new.html')

        code = generate_session_code()
        new_session = Session(
            name=name,
            code=code,
            user_id=session['user_id'], # Use Flask session
            active=True,
            archived=False # Explicitly set archived to False
        )
        db.session.add(new_session)
        db.session.commit()
        flash(f"Session '{name}' created successfully!", "success")
        return redirect(url_for('manage_session', session_id=new_session.id))

    return render_template('session_new.html')

@app.route('/sessions/<int:session_id>')
@login_required
def manage_session(session_id):
    # Query using Flask session for user_id
    # Use 'current_session' to avoid conflict with Flask session
    current_session = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
    # Don't show archived sessions via direct URL unless intended
    if current_session.archived:
        flash("This session is archived.", "info")
        return redirect(url_for('list_sessions')) # Or redirect to archived list

    # Use 'code' instead of 'session_code' in url_for
    join_url = url_for('audience_view', code=current_session.code, _external=True)
    qr_code_data_url = create_qr_code_data(join_url)
    # Pass database session object as 'current_session'
    return render_template('session_manage.html',
                           current_session=current_session,
                           questions=current_session.questions, # Already ordered by model definition
                           join_url=join_url,
                           qr_code_data_url=qr_code_data_url)

@app.route('/present/<int:session_id>')
@login_required
def present_mode(session_id):
    # Query using Flask session for user_id
    # Use 'current_session' to avoid conflict with Flask session
    current_session = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
    # Prevent presenting archived sessions
    if current_session.archived:
        flash("Cannot present an archived session.", "warning")
        return redirect(url_for('manage_session', session_id=session_id))

    active_questions = [q for q in current_session.questions if q.active]
    # Use 'code' instead of 'session_code' in url_for
    join_url = url_for('audience_view', code=current_session.code, _external=True)
    qr_code_data_url = create_qr_code_data(join_url, size=150)
    # Pass database session object as 'current_session'
    return render_template('present_mode.html',
                           current_session=current_session,
                           active_questions=active_questions,
                           join_url=join_url,
                           qr_code_data_url=qr_code_data_url)


# --- Question Routes ---
@app.route('/sessions/<int:session_id>/questions/new/<q_type>', methods=['GET', 'POST'])
@login_required
def new_question(session_id, q_type):
    # Query using Flask session for user_id
    # RENAME db_session to current_session for clarity and consistency
    current_session = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
    # Prevent adding questions to archived sessions
    if current_session.archived:
        flash("Cannot add questions to an archived session.", "warning")
        return redirect(url_for('manage_session', session_id=session_id))

    valid_types = ['multiple_choice', 'word_cloud', 'rating']
    if q_type not in valid_types:
        abort(400, "Invalid question type")

    if request.method == 'POST':
        title = request.form.get('title')
        if not title:
            flash("Question title is required.", "danger")
            # Need to pass type back to template for rendering correct form again
            # Pass current_session
            return render_template('question_new.html', current_session=current_session, q_type=q_type, title=title)

        options_dict_or_list = {} # Default to dict
        if q_type == 'multiple_choice':
            options_text = request.form.get('options', '')
            options_list = [opt.strip() for opt in options_text.splitlines() if opt.strip()]
            if not options_list:
                flash("At least one option is required for multiple choice.", "danger")
                # Pass current_session
                return render_template('question_new.html', current_session=current_session, q_type=q_type, title=title, options=options_text)
            options_dict_or_list = options_list # Store list directly for MC
        elif q_type == 'rating':
            max_rating = request.form.get('max_rating', 5, type=int)
            options_dict_or_list = {'max_rating': max_rating} # Store dict for rating
        # Word cloud needs no specific options initially, empty dict is fine

        new_q = Question(
            session_id=session_id,
            type=q_type,
            title=title,
            options=json.dumps(options_dict_or_list), # Serialize the list or dict
            active=True,
            # Order could be handled here, e.g., max(q.order for q in session.questions) + 1
        )
        db.session.add(new_q)
        db.session.commit()
        flash(f"{q_type.replace('_', ' ').title()} question created.", "success")
        return redirect(url_for('manage_session', session_id=session_id))

    # GET request
    # Pass current_session
    return render_template('question_new.html', current_session=current_session, q_type=q_type)


@app.route('/questions/<int:question_id>/results')
@login_required
def view_question_results(question_id):
    question = Question.query.get_or_404(question_id)
    # Verify ownership through Flask session
    if question.session.user_id != session['user_id']:
        abort(403)
    stats = get_question_stats(question_id) # Use helper to calculate stats
    return render_template('question_results.html', question=question, stats=stats)


# --- Admin Routes ---
@app.route('/admin/users')
@admin_required # Apply both decorators (@login_required is applied within @admin_required)
def admin_manage_users():
    """Displays page for admins to manage users."""
    # Query all users except the current admin
    users = User.query.filter(User.id != session['user_id']).order_by(User.username).all()
    return render_template('admin_users.html', users=users)


# --- API Routes (for toggling status, could use JS fetch or HTMX) ---
@app.route('/api/sessions/<int:session_id>/toggle', methods=['POST'])
@login_required
def api_toggle_session(session_id):
     # Query using Flask session for user_id
    current_session = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
    # Cannot toggle archived sessions
    if current_session.archived:
         return jsonify({"success": False, "message": "Cannot toggle archived session."}), 400
    current_session.active = not current_session.active
    db.session.commit()
    # Return new status or updated HTML fragment if using HTMX
    return jsonify({"success": True, "active": current_session.active, "new_text": "Deactivate" if current_session.active else "Activate"})

@app.route('/api/questions/<int:question_id>/toggle', methods=['POST'])
@login_required
def api_toggle_question(question_id):
    question = Question.query.get_or_404(question_id)
     # Verify ownership through Flask session
    if question.session.user_id != session['user_id']:
        # Return JSON error instead of aborting for API endpoint
        return jsonify({"success": False, "message": "Permission denied."}), 403
    # Cannot toggle questions in archived sessions
    if question.session.archived:
         return jsonify({"success": False, "message": "Cannot toggle question in archived session."}), 400
    question.active = not question.active
    db.session.commit()
    # Return new status or updated HTML fragment if using HTMX
    return jsonify({"success": True, "active": question.active, "new_text": "Deactivate" if question.active else "Activate"})

@app.route('/api/sessions/<int:session_id>/archive', methods=['POST'])
@login_required
def api_archive_session(session_id):
    """API endpoint to toggle session archive status."""
    current_session = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
    current_session.archived = not current_session.archived
    # Optionally deactivate when archiving
    if current_session.archived:
        current_session.active = False
    db.session.commit()
    flash(f"Session '{current_session.name}' {'archived' if current_session.archived else 'unarchived'}.", "info")
    # Redirect is simpler here than complex JS to update UI across lists
    # Redirect to the appropriate list based on the new status
    if current_session.archived:
        return redirect(url_for('list_sessions'))
    else:
        # If unarchiving, maybe redirect back to the archived list or the main list
        return redirect(request.referrer or url_for('list_archived_sessions'))


# --- Admin API Routes ---
@app.route('/api/users/<int:user_id>/toggle_verify', methods=['POST'])
@admin_required # Ensures only logged-in admins can access
def api_toggle_verify_user(user_id):
    """API endpoint for admin to toggle user verification status."""
    user_to_modify = db.session.get(User, user_id) # Use newer Session.get()
    if not user_to_modify:
        return jsonify({"success": False, "message": "User not found."}), 404
    # Prevent admin from de-verifying themselves? Optional.
    # if user_to_modify.id == session['user_id']:
    #     return jsonify({"success": False, "message": "Cannot change own verification status."}), 400
    user_to_modify.is_verified = not user_to_modify.is_verified
    db.session.commit()
    return jsonify({
        "success": True,
        "verified": user_to_modify.is_verified,
        "new_text": "Unverify" if user_to_modify.is_verified else "Verify"
    })

@app.route('/api/users/<int:user_id>/toggle_archive', methods=['POST'])
@admin_required # Ensures only logged-in admins can access
def api_toggle_archive_user(user_id):
    """API endpoint for admin to toggle user archive status."""
    user_to_modify = db.session.get(User, user_id) # Use newer Session.get()
    if not user_to_modify:
        return jsonify({"success": False, "message": "User not found."}), 404
    # Prevent admin from archiving themselves
    if user_to_modify.id == session['user_id']:
        return jsonify({"success": False, "message": "Cannot archive self."}), 400
    user_to_modify.is_archived = not user_to_modify.is_archived
    # Optionally force logout if user is archived? More complex.
    db.session.commit()
    return jsonify({
        "success": True,
        "archived": user_to_modify.is_archived,
        "new_text": "Unarchive" if user_to_modify.is_archived else "Archive"
    })


# --- Audience Routes ---
@app.route('/join', methods=['GET', 'POST'])
def join():
    if request.method == 'POST':
        code = request.form.get('code', '').upper()
        # Use current_session as variable name, check not archived
        current_session = Session.query.filter_by(code=code, active=True, archived=False).first()

        if current_session:
            # Generate respondent ID if not present
            respondent_id = request.cookies.get(RESPONDENT_COOKIE_NAME)
            if not respondent_id:
                respondent_id = str(uuid.uuid4())

            response = make_response(redirect(url_for('audience_view', code=code))) # Use 'code' here
            response.set_cookie(RESPONDENT_COOKIE_NAME, respondent_id, max_age=60*60*24*30) # 30 days
            return response
        else:
            flash("Invalid, inactive, or archived session code. Please try again.", "danger")
            return render_template('join.html', code=code)

    return render_template('join.html')


@app.route('/audience/<code>')
def audience_view(code):
    session_code = code.upper()
    # Use current_session as variable name, check not archived
    current_session = Session.query.filter_by(code=session_code, active=True, archived=False).first()
    if not current_session:
        flash("Session not found, is inactive, or has been archived.", "warning")
        return redirect(url_for('join'))

    respondent_id = request.cookies.get(RESPONDENT_COOKIE_NAME)
    if not respondent_id:
        # Force back to join page to get a cookie
        flash("Could not identify you. Please join the session again.", "warning")
        return redirect(url_for('join'))

    active_questions = [q for q in current_session.questions if q.active]

    # Get previous responses for this user in this session
    previous_responses_db = Response.query.filter_by(session_id=current_session.id, respondent_id=respondent_id).all()
    previous_responses = {r.question_id: r.response_value for r in previous_responses_db}

    # Pass current_session to the template
    return render_template('audience_view.html',
                           current_session=current_session,
                           questions=active_questions,
                           previous_responses=previous_responses)


@app.route('/audience/respond/<int:question_id>', methods=['POST'])
def process_response(question_id):
    question = Question.query.get_or_404(question_id)
    # Check if question or session is inactive or archived
    if not question.active or not question.session.active or question.session.archived:
        flash("Sorry, this question or session is no longer active.", "warning")
        return redirect(url_for('audience_view', code=question.session.code)) # Redirect back

    respondent_id = request.cookies.get(RESPONDENT_COOKIE_NAME)
    if not respondent_id:
        flash("Could not identify you. Please try rejoining the session.", "warning")
        return redirect(url_for('join'))

    response_value = request.form.get(f'response-{question_id}')
    if response_value is None:
        flash("No response value submitted.", "warning")
        return redirect(url_for('audience_view', code=question.session.code))

    # Check for existing response and update, or create new
    existing_response = Response.query.filter_by(
        question_id=question_id,
        respondent_id=respondent_id
    ).first()

    if existing_response:
        existing_response.response_value = response_value
        existing_response.created_at = datetime.now().isoformat()
    else:
        new_response = Response(
            question_id=question_id,
            session_id=question.session_id,
            response_value=response_value,
            respondent_id=respondent_id
        )
        db.session.add(new_response)

    db.session.commit()

    # Notify presenters via WebSocket
    broadcast_results(question_id)

    # Using flash for confirmation, could return JSON for JS/HTMX
    flash(f"Your response was submitted!", "success")
    return redirect(url_for('audience_view', code=question.session.code))


# --- Data Export Routes ---
@app.route('/questions/<int:question_id>/export')
@login_required
def export_question_results(question_id):
    question = Question.query.get_or_404(question_id)
     # Verify ownership through Flask session
    if question.session.user_id != session['user_id']: abort(403)

    all_responses = Response.query.filter_by(question_id=question_id).order_by(Response.created_at).all()
    if not all_responses:
        flash("No responses to export for this question.", "info")
        return redirect(url_for('view_question_results', question_id=question_id))

    data_to_export = [
        {
            "response_id": r.id, "question_id": r.question_id, "session_id": r.session_id,
            "response_value": r.response_value, "respondent_id": r.respondent_id,
            "timestamp": r.created_at
        } for r in all_responses
    ]

    output = io.StringIO()
    fieldnames = data_to_export[0].keys()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data_to_export)

    mem_output = io.BytesIO()
    mem_output.write(output.getvalue().encode('utf-8'))
    mem_output.seek(0)
    output.close()

    filename = f"classpulse_q_{question_id}_results.csv"
    return send_file(mem_output, as_attachment=True, download_name=filename, mimetype='text/csv')


@app.route('/sessions/<int:session_id>/export')
@login_required
def export_session_results(session_id):
     # Query using Flask session for user_id
    current_session = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
    all_responses = Response.query.filter_by(session_id=session_id).order_by(Response.question_id, Response.created_at).all()

    if not all_responses:
        flash("No responses to export for this session.", "info")
        return redirect(url_for('manage_session', session_id=session_id))

    data_to_export = [
        {
            "response_id": r.id, "question_id": r.question_id, "session_id": r.session_id,
            "response_value": r.response_value, "respondent_id": r.respondent_id,
            "timestamp": r.created_at
        } for r in all_responses
    ]

    output = io.StringIO()
    fieldnames = data_to_export[0].keys()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data_to_export)

    mem_output = io.BytesIO()
    mem_output.write(output.getvalue().encode('utf-8'))
    mem_output.seek(0)
    output.close()

    filename = f"classpulse_session_{session_id}_all_results.csv"
    return send_file(mem_output, as_attachment=True, download_name=filename, mimetype='text/csv')


# --- WebSocket Handling ---

# Helper to get stats (could be moved to a utils file)
def get_question_stats(question_id: int) -> Dict[str, Any]:
    """Gets statistics for a question based on its type."""
    # Use with app.app_context() if calling this outside a request context
    question = db.session.get(Question, question_id) # Use newer Session.get()
    if not question:
        return {"error": "Question not found"}

    all_responses = Response.query.filter_by(question_id=question_id).all()
    total_responses = len(all_responses)
    stats: Dict[str, Any] = {"total_responses": total_responses, "type": question.type, "title": question.title}

    if question.type == 'multiple_choice':
        try:
            options = json.loads(question.options) # Should be a list
            if not isinstance(options, list): options = []
        except json.JSONDecodeError:
            options = []
        # Ensure options are strings for dictionary keys
        options = [str(opt) for opt in options]
        results = {opt: 0 for opt in options}
        for resp in all_responses:
            if str(resp.response_value) in results: # Ensure comparison is string-to-string
                results[str(resp.response_value)] += 1
        stats["results"] = results
        stats["options"] = options # Keep original options list for labels

    elif question.type == 'word_cloud':
        words = {}
        for resp in all_responses:
            # Simple split by space, convert to lowercase, filter stop words
            for word in resp.response_value.lower().split():
                cleaned_word = ''.join(filter(str.isalnum, word)) # Basic cleaning
                if cleaned_word and cleaned_word not in STOP_WORDS: # Filter stop words
                    words[cleaned_word] = words.get(cleaned_word, 0) + 1
        # Ensure results are in the format jQCloud expects
        stats["results"] = [{"text": w, "weight": c} for w, c in words.items()]

    elif question.type == 'rating':
        try:
            config = json.loads(question.options) # Should be a dict
            max_rating = int(config.get('max_rating', 5)) # Ensure integer
        except (json.JSONDecodeError, AttributeError, ValueError):
            max_rating = 5
        results = {str(i): 0 for i in range(1, max_rating + 1)}
        for resp in all_responses:
             # Ensure comparison is string-to-string
            if str(resp.response_value) in results:
                results[str(resp.response_value)] += 1
        stats["results"] = results
        stats["max_rating"] = max_rating

    return stats

# Function to broadcast results to a specific room (question)
def broadcast_results(question_id: int):
    """Fetches latest stats and emits them to the question's room."""
    print(f"Broadcasting results for question {question_id}")
    # Need app context to access db outside of a request
    with app.app_context():
        stats = get_question_stats(question_id)
    room_name = f'question_{question_id}'
    # Make sure stats are JSON serializable (datetime objects are not by default)
    # In this case, our stats dict should be fine.
    socketio.emit('update_results', {'question_id': question_id, 'stats': stats}, room=room_name)
    print(f"Emitted update for room {room_name}")


@socketio.on('connect')
def handle_connect():
    # Authentication check could happen here if needed for presenters
    # Accessing flask session in socketio requires proper setup or passing tokens
    # For simplicity, we'll just log the connection SID for now.
    # user_id = session.get('user_id') # This might not work reliably depending on setup
    # if user_id:
    #     print(f"Presenter {user_id} connected: {request.sid}")
    # else:
    #      print(f"Audience member or anonymous user connected: {request.sid}")
    print(f"Client connected: {request.sid}")


@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")
    # No specific room cleanup needed here as rooms are managed by join/leave

@socketio.on('join')
def handle_join_room(data):
    """Client requests to join a room for a specific question."""
    question_id = data.get('question_id')
    if question_id:
        try:
            q_id = int(question_id) # Ensure it's an integer
            room_name = f'question_{q_id}'
            join_room(room_name)
            print(f"Client {request.sid} joined room {room_name}")
            # Send current results immediately to the joining client
            # Need app context to access db outside of a request
            with app.app_context():
                stats = get_question_stats(q_id)
            emit('update_results', {'question_id': q_id, 'stats': stats}, room=request.sid) # Send only to requester
        except ValueError:
            print(f"Invalid question_id received for join: {question_id}")
        except Exception as e:
             print(f"Error handling join room for question {question_id}: {e}")


@socketio.on('leave')
def handle_leave_room(data):
    """Client requests to leave a room."""
    question_id = data.get('question_id')
    if question_id:
        try:
            q_id = int(question_id)
            room_name = f'question_{q_id}'
            leave_room(room_name)
            print(f"Client {request.sid} left room {room_name}")
        except ValueError:
             print(f"Invalid question_id received for leave: {question_id}")
        except Exception as e:
            print(f"Error handling leave room for question {question_id}: {e}")


# --- Initialization ---
def create_default_admin():
    """Creates the default admin user if none exists."""
    with app.app_context():
        admin_exists = User.query.filter_by(username=DEFAULT_ADMIN_USER).first()
        if not admin_exists:
            print(f"Creating default admin user: {DEFAULT_ADMIN_USER} / {DEFAULT_ADMIN_PASS}")
            password_h = hash_password(DEFAULT_ADMIN_PASS)
            admin = User(
                username=DEFAULT_ADMIN_USER,
                password_hash=password_h,
                email="admin@example.com",
                display_name="Admin User",
                is_admin=True,      # Make default user admin
                is_verified=True,   # Make default user verified
                is_archived=False
            )
            db.session.add(admin)
            try:
                db.session.commit()
                print("Default admin user created successfully.")
            except Exception as e:
                db.session.rollback()
                print(f"Failed to create default admin user: {e}")

# --- Run Application ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Create database tables if they don't exist
    create_default_admin()
    # Use eventlet or gevent for SocketIO
    # Example using eventlet: pip install eventlet
    print("Starting Flask-SocketIO server on http://localhost:5002")
    # Set use_reloader=False if reloading causes issues with SocketIO/DB creation
    # Set async_mode='threading' or 'eventlet' or 'gevent' based on installation
    # Added allow_unsafe_werkzeug=True for newer SocketIO/Werkzeug versions if needed
    # Note: use_reloader=True might cause create_default_admin to run twice
    socketio.run(app, host='0.0.0.0', port=5002, debug=True, use_reloader=False, allow_unsafe_werkzeug=True) # Changed use_reloader to False



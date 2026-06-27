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

# Load environment variables from a .env file if present (no-op if missing).
# This makes the variables documented in .env.example actually take effect.
from dotenv import load_dotenv
load_dotenv()

# Flask and Extensions
from flask import (
    Flask, render_template, request, redirect, url_for, session,
    flash, make_response, jsonify, abort, send_file, g # Added g for admin check
)
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# External Libraries (Ensure these are installed)
import qrcode as qr_code_lib
from PIL import Image
import base64
import requests

# --- Flask App Configuration ---
app = Flask(__name__)

# SECRET_KEY signs the session cookie (which stores user_id), so a known or
# shared key lets anyone forge a session and impersonate any user/admin. It MUST
# come from the environment in production. If unset, we fall back to an ephemeral
# random key so local/dev runs still work — but that key does not survive a
# restart and differs across gunicorn workers, so logins break. We warn loudly.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
_SECRET_KEY_IS_EPHEMERAL = not app.config['SECRET_KEY']
if _SECRET_KEY_IS_EPHEMERAL:
    app.config['SECRET_KEY'] = secrets.token_hex(32)

app.config['SQLALCHEMY_DATABASE_URI'] = (
    os.environ.get('DATABASE_URL') or 'sqlite:///classpulse_flask.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Session cookie hardening. Secure is opt-in via env so local HTTP dev still
# works; set SESSION_COOKIE_SECURE=true when serving over HTTPS.
COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', '').lower() in ('1', 'true', 'yes')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = COOKIE_SECURE

if _SECRET_KEY_IS_EPHEMERAL:
    app.logger.warning(
        "SECRET_KEY is not set; generated a temporary key. Sessions will not "
        "survive restarts and will break across multiple workers. Set SECRET_KEY "
        "in the environment (or .env) for any non-trivial deployment."
    )

# --- CSRF Protection ---
# Protects all state-changing requests (forms + AJAX). Tokens have no time limit
# so long-lived presentation/audience pages don't fail mid-session on submit.
app.config['WTF_CSRF_TIME_LIMIT'] = None
csrf = CSRFProtect(app)

# --- Rate Limiting ---
# Default in-memory store: adequate for a single-process classroom deployment.
# For multi-worker gunicorn, set RATELIMIT_STORAGE_URI (e.g. redis://...).
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=os.environ.get('RATELIMIT_STORAGE_URI', 'memory://'),
    default_limits=[],
)

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
    deleted = db.Column(db.Boolean, default=False, nullable=False) # New field for soft deletion
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
# Bootstrap admin credentials come from the environment. There is deliberately
# NO hardcoded default password: if DEFAULT_ADMIN_PASS is unset, a strong random
# password is generated on first run and printed once to the logs.
DEFAULT_ADMIN_USER = os.environ.get("DEFAULT_ADMIN_USER", "admin")
DEFAULT_ADMIN_PASS = os.environ.get("DEFAULT_ADMIN_PASS")  # may be None -> random
RESPONDENT_COOKIE_NAME = "classpulse_respondent"

# --- AI Provider Configuration (global, set via environment) ---
# One provider serves the whole deployment (configured in .env, not per-user).
# Two adapter families cover essentially every model:
#   openai    -> POST {AI_BASE_URL}/chat/completions, "Authorization: Bearer"
#                (OpenAI, Ollama's /v1, Groq, Together, vLLM, OpenRouter, ...).
#                Leave AI_API_KEY blank for a local/keyless Ollama.
#   anthropic -> POST {AI_BASE_URL}/messages, "x-api-key" + "anthropic-version"
#                (api.anthropic.com direct).
# Both AI_BASE_URL values are the "/v1" root; the adapter appends the endpoint.
AI_PROVIDER = os.environ.get("AI_PROVIDER", "").strip().lower()
AI_BASE_URL = os.environ.get("AI_BASE_URL", "").strip().rstrip("/")
AI_API_KEY = os.environ.get("AI_API_KEY", "").strip()
AI_MODEL = os.environ.get("AI_MODEL", "").strip()

AI_CONFIGURED = AI_PROVIDER in ("openai", "anthropic") and bool(AI_BASE_URL and AI_MODEL)
_ai_enabled_raw = os.environ.get("AI_ENABLED", "").strip().lower()
AI_ENABLED = (_ai_enabled_raw in ("1", "true", "yes")) if _ai_enabled_raw else AI_CONFIGURED

if AI_ENABLED:
    app.logger.info(f"AI question generation enabled: provider={AI_PROVIDER} model={AI_MODEL}")
elif AI_PROVIDER or AI_BASE_URL or AI_MODEL:
    app.logger.warning(
        "AI is partially configured but disabled. Set AI_PROVIDER to 'openai' or "
        "'anthropic', plus AI_BASE_URL and AI_MODEL (see .env.example)."
    )

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
    return {'current_user': user, 'is_admin': is_admin, 'ai_enabled': AI_ENABLED}

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

# --- AI Service Functions ---

def call_openai_compatible_api(base_url: str, api_key: str, model: str, prompt: str) -> Dict[str, Any]:
    """Call an OpenAI-compatible /chat/completions endpoint.

    Covers OpenAI, Ollama's /v1, Groq, Together, vLLM, OpenRouter, etc. The
    Authorization header is omitted when no key is supplied, so a local/keyless
    Ollama works unchanged. `base_url` is the "/v1" root; "/chat/completions"
    is appended here.
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that generates educational questions. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            },
            timeout=30
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return {"success": True, "response": content}
    except Exception as e:
        return {"success": False, "error": str(e)}


def call_anthropic_api(base_url: str, api_key: str, model: str, prompt: str) -> Dict[str, Any]:
    """Call an Anthropic-native /messages endpoint (api.anthropic.com direct).

    `base_url` is the "/v1" root; "/messages" is appended here. Auth uses the
    x-api-key header plus the required anthropic-version.
    """
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(
            f"{base_url}/messages",
            headers=headers,
            json={
                "model": model,
                "max_tokens": 500,
                "system": "You are a helpful assistant that generates educational questions. Always respond with valid JSON.",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["content"][0]["text"]
        return {"success": True, "response": content}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Dispatch table for the configured provider. Both AI_BASE_URL values are the
# "/v1" root; each adapter appends its own endpoint path.
_AI_ADAPTERS = {
    "openai": call_openai_compatible_api,
    "anthropic": call_anthropic_api,
}


def call_ai(prompt: str) -> Dict[str, Any]:
    """Generate a raw completion from the globally-configured AI provider."""
    adapter = _AI_ADAPTERS.get(AI_PROVIDER)
    if adapter is None:
        return {"success": False, "error": f"Unknown AI provider: {AI_PROVIDER!r}"}
    return adapter(AI_BASE_URL, AI_API_KEY, AI_MODEL, prompt)

def parse_ai_response(response_text: str) -> Dict[str, Any]:
    """Parses AI response and extracts question data."""
    try:
        # Try to extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            data = json.loads(json_str)
            
            # Validate required fields
            if "question_type" in data and "title" in data:
                question_type = data["question_type"].lower().replace(" ", "_")
                if question_type in ["multiple_choice", "word_cloud", "rating"]:
                    return {
                        "success": True,
                        "question_type": question_type,
                        "title": data["title"][:255],  # Limit length
                        "options": data.get("options", []),
                        "confidence": data.get("confidence", 0.8)
                    }
        
        return {"success": False, "error": "Could not parse valid question format from AI response"}
    except Exception as e:
        return {"success": False, "error": f"Error parsing AI response: {str(e)}"}

def generate_question_prompt(user_input: str) -> str:
    """Generates the prompt for AI question generation."""
    return f"""Analyze this prompt and generate an educational question: '{user_input}'

Respond in JSON format only:
{{
  "question_type": "multiple_choice" | "word_cloud" | "rating",
  "title": "the question text (clear and concise)",
  "options": [...] for multiple_choice, {{"max_rating": 5}} for rating, [] for word_cloud,
  "confidence": 0.0-1.0
}}

Guidelines:
- For multiple_choice: Include 4 realistic options in the "options" array
- For word_cloud: Use a single prompt word/phrase that will generate interesting responses
- For rating: Include max_rating in options object (typically 5 or 10)
- Set confidence < 0.5 if the question type is unclear from the prompt
- Keep questions educational and appropriate"""

def generate_question_with_ai(user_input: str) -> Dict[str, Any]:
    """Generate a question via the globally-configured AI provider."""
    if not AI_ENABLED:
        return {"success": False, "error": "AI question generation is not configured."}
    prompt = generate_question_prompt(user_input)
    result = call_ai(prompt)
    if result["success"]:
        return parse_ai_response(result["response"])
    return {"success": False, "error": result.get("error", "AI request failed.")}

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
@limiter.limit("10 per minute", methods=["POST"])
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

@app.route('/logout', methods=['POST'])
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
        if len(password or "") < 10: errors.append("Password must be at least 10 characters long.")
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

@app.route('/api/test-ai-generation', methods=['POST'])
@login_required
def api_test_ai_generation():
    """API endpoint to test AI question generation."""
    try:
        data = request.get_json()
        if not data or 'prompt' not in data:
            return jsonify({"success": False, "error": "No prompt provided"}), 400
        
        result = generate_question_with_ai(data['prompt'])
        return jsonify(result)
    except Exception:
        app.logger.exception("AI test generation failed")
        return jsonify({"success": False, "error": "Question generation failed."}), 500


# --- Serialization helpers (used by the unified dashboard + its AJAX API) ---
def _question_to_dict(q):
    """Serialize a Question for the builder UI."""
    try:
        parsed = json.loads(q.options) if q.options else {}
    except (json.JSONDecodeError, TypeError):
        parsed = {}
    data = {
        'id': q.id,
        'type': q.type,
        'title': q.title,
        'active': q.active,
        'response_count': Response.query.filter_by(question_id=q.id).count(),
        'options': parsed if (q.type == 'multiple_choice' and isinstance(parsed, list)) else [],
        'max_rating': 5,
    }
    if q.type == 'rating' and isinstance(parsed, dict):
        try:
            data['max_rating'] = int(parsed.get('max_rating', 5))
        except (ValueError, TypeError):
            data['max_rating'] = 5
    return data


def _session_to_dict(s, include_questions=False):
    d = {
        'id': s.id, 'name': s.name, 'code': s.code,
        'active': s.active, 'archived': s.archived,
        'question_count': len(s.questions),
    }
    if include_questions:
        d['questions'] = [_question_to_dict(q) for q in s.questions]
    return d


def _parse_question_payload(data):
    """Validate/normalise an add/edit question payload.
    Returns (error_message_or_None, q_type, title, options_value)."""
    q_type = data.get('type')
    if q_type not in ('multiple_choice', 'word_cloud', 'rating'):
        return ('Invalid question type.', None, None, None)
    title = (data.get('title') or '').strip()
    if not title:
        return ('Question title is required.', None, None, None)
    if q_type == 'multiple_choice':
        opts = data.get('options') or []
        if isinstance(opts, str):
            opts = opts.splitlines()
        opts = [str(o).strip() for o in opts if str(o).strip()]
        if len(opts) < 2:
            return ('Add at least two options.', None, None, None)
        return (None, q_type, title, opts)
    if q_type == 'rating':
        try:
            mx = int(data.get('max_rating', 5))
        except (ValueError, TypeError):
            mx = 5
        return (None, q_type, title, {'max_rating': max(2, min(10, mx))})
    return (None, q_type, title, {})  # word_cloud carries no config


def _render_dashboard(selected_id=None):
    """Render the unified master-detail dashboard. Used at / (no selection) and
    /sessions/<id> (a session selected, which doubles as the deep link)."""
    user_id = session['user_id']
    # Include archived (client filters via the Active/Archived tabs); exclude deleted.
    user_sessions = Session.query.filter_by(user_id=user_id, deleted=False).order_by(Session.created_at.desc()).all()
    sessions_data = [_session_to_dict(s) for s in user_sessions]
    selected = None
    if selected_id is not None:
        sel = next((s for s in user_sessions if s.id == selected_id), None)
        if sel:
            selected = _session_to_dict(sel, include_questions=True)
            selected['join_url'] = url_for('audience_view', code=sel.code, _external=True)
            selected['qr'] = create_qr_code_data(selected['join_url'])
    return render_template('dashboard.html', sessions=sessions_data, selected=selected)


# --- Presenter Routes ---
@app.route('/')
@login_required
def dashboard():
    return _render_dashboard()

@app.route('/sessions')
@login_required
def list_sessions():
    user_id = session['user_id'] # Use Flask session
    # Filter out archived and deleted sessions
    user_sessions = Session.query.filter_by(user_id=user_id, archived=False, deleted=False).order_by(Session.created_at.desc()).all()
    return render_template('sessions_list.html', sessions=user_sessions)

# Optional: Route to view archived sessions
@app.route('/sessions/archived')
@login_required
def list_archived_sessions():
    user_id = session['user_id']
    archived_sessions = Session.query.filter_by(user_id=user_id, archived=True, deleted=False).order_by(Session.created_at.desc()).all()
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
            archived=False, # Explicitly set archived to False
            deleted=False  # Explicitly set deleted to False
        )
        db.session.add(new_session)
        db.session.commit()
        flash(f"Session '{name}' created successfully!", "success")
        return redirect(url_for('manage_session', session_id=new_session.id))

    return render_template('session_new.html')

@app.route('/sessions/<int:session_id>')
@login_required
def manage_session(session_id):
    # The session builder is the unified dashboard with this session selected;
    # this URL is also the shareable deep link.
    current_session = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
    if current_session.deleted:
        flash("This session has been deleted.", "warning")
        return redirect(url_for('dashboard'))
    return _render_dashboard(selected_id=session_id)

@app.route('/present/<int:session_id>')
@login_required
def present_mode(session_id):
    # Query using Flask session for user_id
    # Use 'current_session' to avoid conflict with Flask session
    current_session = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
    # Prevent presenting archived or deleted sessions
    if current_session.archived:
        flash("Cannot present an archived session.", "warning")
        return redirect(url_for('manage_session', session_id=session_id))
    if current_session.deleted:
        flash("Cannot present a deleted session.", "warning")
        return redirect(url_for('list_sessions'))

    active_questions = [q for q in current_session.questions if q.active]
    # Use 'code' instead of 'session_code' in url_for
    join_url = url_for('audience_view', code=current_session.code, _external=True)
    qr_code_data_url = create_qr_code_data(join_url, size=150)
    # Pass database session object as 'current_session'
    return render_template('present_mode.html',
                           current_session=current_session,
                           active_questions=active_questions,
                           join_url=join_url,
                           qr_code_data_url=qr_code_data_url,
                           mode='present')


@app.route('/sessions/<int:session_id>/results')
@login_required
def session_results(session_id):
    """Post-hoc results view — same Focus/Grid/Stack layouts as Present, over
    all questions, available even when the session is no longer active."""
    current_session = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
    if current_session.deleted:
        flash("This session has been deleted.", "warning")
        return redirect(url_for('dashboard'))
    return render_template('present_mode.html',
                           current_session=current_session,
                           active_questions=list(current_session.questions),
                           join_url=None,
                           qr_code_data_url=None,
                           mode='results')


# --- Question Routes ---
@app.route('/sessions/<int:session_id>/questions/new/<q_type>', methods=['GET', 'POST'])
@login_required
def new_question(session_id, q_type):
    # Query using Flask session for user_id
    # RENAME db_session to current_session for clarity and consistency
    current_session = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
    # Prevent adding questions to archived or deleted sessions
    if current_session.archived:
        flash("Cannot add questions to an archived session.", "warning")
        return redirect(url_for('manage_session', session_id=session_id))
    if current_session.deleted:
        flash("Cannot add questions to a deleted session.", "warning")
        return redirect(url_for('list_sessions'))

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
    # Cannot toggle archived or deleted sessions
    if current_session.archived:
         return jsonify({"success": False, "message": "Cannot toggle archived session."}), 400
    if current_session.deleted:
         return jsonify({"success": False, "message": "Cannot toggle deleted session."}), 400
    current_session.active = not current_session.active
    db.session.commit()
    # Notify audience members so an inactive session boots them out live
    broadcast_questions_changed(current_session.id)
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
    # Cannot toggle questions in archived or deleted sessions
    if question.session.archived:
         return jsonify({"success": False, "message": "Cannot toggle question in archived session."}), 400
    if question.session.deleted:
         return jsonify({"success": False, "message": "Cannot toggle question in deleted session."}), 400
    question.active = not question.active
    db.session.commit()
    # Push the new active-question set to any audience members watching live
    broadcast_questions_changed(question.session_id)
    # Return new status or updated HTML fragment if using HTMX
    return jsonify({"success": True, "active": question.active, "new_text": "Deactivate" if question.active else "Activate"})

@app.route('/api/sessions/<int:session_id>/archive', methods=['POST'])
@login_required
def api_archive_session(session_id):
    """API endpoint to toggle session archive status."""
    current_session = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
    # Cannot archive deleted sessions
    if current_session.deleted:
        flash("Cannot archive a deleted session.", "warning")
        return redirect(url_for('list_sessions'))
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

@app.route('/api/questions/<int:question_id>/delete', methods=['POST'])
@login_required
def api_delete_question(question_id):
    """API endpoint to delete a question (only if no responses exist)."""
    question = Question.query.get_or_404(question_id)
    # Verify ownership through Flask session
    if question.session.user_id != session['user_id']:
        return jsonify({"success": False, "message": "Permission denied."}), 403
    
    # Cannot delete questions in archived or deleted sessions
    if question.session.archived or question.session.deleted:
        return jsonify({"success": False, "message": "Cannot delete question in archived or deleted session."}), 400
    
    # Check if question has any responses
    response_count = Response.query.filter_by(question_id=question_id).count()
    if response_count > 0:
        return jsonify({
            "success": False, 
            "message": f"Cannot delete question with {response_count} response(s). Deactivate instead."
        }), 400
    
    # Safe to delete - no responses exist
    session_id = question.session_id
    question_title = question.title
    db.session.delete(question)
    db.session.commit()
    # A deleted question may have been active; refresh audience views
    broadcast_questions_changed(session_id)

    flash(f"Question '{question_title}' deleted successfully.", "success")
    return jsonify({"success": True, "message": "Question deleted successfully."})

@app.route('/api/sessions/<int:session_id>/delete', methods=['POST'])
@login_required
def api_delete_session(session_id):
    """API endpoint to delete a session (soft delete with data, hard delete if empty)."""
    current_session = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
    
    # Cannot delete already deleted sessions
    if current_session.deleted:
        return jsonify({"success": False, "message": "Session is already deleted."}), 400
    
    # Check if session has any responses
    response_count = Response.query.filter_by(session_id=session_id).count()
    
    if response_count > 0:
        # Soft delete - has responses, so preserve data
        current_session.deleted = True
        current_session.active = False  # Deactivate when soft deleting
        db.session.commit()
        flash(f"Session '{current_session.name}' moved to trash (has {response_count} responses).", "info")
        return redirect(url_for('list_sessions'))
    else:
        # Hard delete - no responses, safe to permanently delete
        session_name = current_session.name
        # Delete all questions first (cascade should handle this, but being explicit)
        Question.query.filter_by(session_id=session_id).delete()
        db.session.delete(current_session)
        db.session.commit()
        flash(f"Session '{session_name}' permanently deleted (no responses).", "info")
        return redirect(url_for('list_sessions'))


# --- Session/Question authoring API (used by the unified dashboard) ---
@app.route('/api/sessions', methods=['POST'])
@login_required
def api_create_session():
    """Create a new (inactive) session and return it for the builder."""
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or 'Untitled session').strip() or 'Untitled session'
    s = Session(name=name, code=generate_session_code(), user_id=session['user_id'],
                active=False, archived=False, deleted=False)
    db.session.add(s)
    db.session.commit()
    return jsonify({"success": True, "session": _session_to_dict(s, include_questions=True)})


@app.route('/api/sessions/<int:session_id>/rename', methods=['POST'])
@login_required
def api_rename_session(session_id):
    s = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
    name = ((request.get_json(silent=True) or {}).get('name') or '').strip()
    if not name:
        return jsonify({"success": False, "message": "Name is required."}), 400
    s.name = name
    db.session.commit()
    return jsonify({"success": True, "name": s.name})


@app.route('/api/sessions/<int:session_id>/questions', methods=['GET', 'POST'])
@login_required
def api_session_questions(session_id):
    s = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
    if request.method == 'GET':
        return jsonify({"success": True, "questions": [_question_to_dict(q) for q in s.questions]})
    # POST: create
    if s.archived or s.deleted:
        return jsonify({"success": False, "message": "Cannot add questions to this session."}), 400
    err, q_type, title, opts = _parse_question_payload(request.get_json(silent=True) or {})
    if err:
        return jsonify({"success": False, "message": err}), 400
    next_order = max([q.order for q in s.questions], default=0) + 1
    q = Question(session_id=s.id, type=q_type, title=title, options=json.dumps(opts),
                 active=True, order=next_order)
    db.session.add(q)
    db.session.commit()
    return jsonify({"success": True, "question": _question_to_dict(q)})


@app.route('/api/questions/<int:question_id>/edit', methods=['POST'])
@login_required
def api_edit_question(question_id):
    q = Question.query.get_or_404(question_id)
    if q.session.user_id != session['user_id']:
        return jsonify({"success": False, "message": "Permission denied."}), 403
    if q.session.archived or q.session.deleted:
        return jsonify({"success": False, "message": "Cannot edit this question."}), 400
    err, q_type, title, opts = _parse_question_payload(request.get_json(silent=True) or {})
    if err:
        return jsonify({"success": False, "message": err}), 400
    # Title can always change; structural edits are blocked once responses exist
    # (they would orphan the recorded answers) — duplicate instead.
    structural = (q_type != q.type) or (json.dumps(opts) != (q.options or ''))
    if structural and Response.query.filter_by(question_id=q.id).count() > 0:
        q.title = title
        db.session.commit()
        return jsonify({"success": False, "partial": True,
                        "message": "Saved the title. Options/type can't change once responses exist — duplicate the question instead.",
                        "question": _question_to_dict(q)})
    q.type, q.title, q.options = q_type, title, json.dumps(opts)
    db.session.commit()
    return jsonify({"success": True, "question": _question_to_dict(q)})


@app.route('/api/questions/<int:question_id>/duplicate', methods=['POST'])
@login_required
def api_duplicate_question(question_id):
    q = Question.query.get_or_404(question_id)
    if q.session.user_id != session['user_id']:
        return jsonify({"success": False, "message": "Permission denied."}), 403
    if q.session.archived or q.session.deleted:
        return jsonify({"success": False, "message": "Cannot modify this session."}), 400
    next_order = max([x.order for x in q.session.questions], default=0) + 1
    c = Question(session_id=q.session_id, type=q.type, title=f"{q.title} (copy)",
                 options=q.options, active=True, order=next_order)
    db.session.add(c)
    db.session.commit()
    return jsonify({"success": True, "question": _question_to_dict(c)})


@app.route('/api/sessions/<int:session_id>/questions/reorder', methods=['POST'])
@login_required
def api_reorder_questions(session_id):
    s = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
    order = (request.get_json(silent=True) or {}).get('order') or []
    pos = {qid: i for i, qid in enumerate(order)}
    for q in s.questions:
        if q.id in pos:
            q.order = pos[q.id]
    db.session.commit()
    return jsonify({"success": True})


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
        # Use current_session as variable name, check not archived or deleted
        current_session = Session.query.filter_by(code=code, active=True, archived=False, deleted=False).first()

        if current_session:
            # Generate respondent ID if not present
            respondent_id = request.cookies.get(RESPONDENT_COOKIE_NAME)
            if not respondent_id:
                respondent_id = str(uuid.uuid4())

            response = make_response(redirect(url_for('audience_view', code=code))) # Use 'code' here
            response.set_cookie(
                RESPONDENT_COOKIE_NAME,
                respondent_id,
                max_age=60 * 60 * 24 * 30,  # 30 days
                httponly=True,
                samesite='Lax',
                secure=COOKIE_SECURE,
            )
            return response
        else:
            flash("Invalid, inactive, archived, or deleted session code. Please try again.", "danger")
            return render_template('join.html', code=code)

    return render_template('join.html')


@app.route('/audience/<code>')
def audience_view(code):
    session_code = code.upper()
    # Use current_session as variable name, check not archived or deleted
    current_session = Session.query.filter_by(code=session_code, active=True, archived=False, deleted=False).first()
    if not current_session:
        flash("Session not found, is inactive, archived, or has been deleted.", "warning")
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
                           active_question_ids=[q.id for q in active_questions],
                           previous_responses=previous_responses)


@app.route('/audience/respond/<int:question_id>', methods=['POST'])
def process_response(question_id):
    # Audience view submits via fetch() with this header; fall back to the
    # classic redirect/flash flow for non-JS clients.
    wants_json = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    question = Question.query.get_or_404(question_id)
    # Check if question or session is inactive, archived, or deleted
    if not question.active or not question.session.active or question.session.archived or question.session.deleted:
        msg = "Sorry, this question or session is no longer active."
        if wants_json:
            return jsonify({"success": False, "message": msg, "inactive": True}), 409
        flash(msg, "warning")
        return redirect(url_for('audience_view', code=question.session.code)) # Redirect back

    respondent_id = request.cookies.get(RESPONDENT_COOKIE_NAME)
    if not respondent_id:
        msg = "Could not identify you. Please try rejoining the session."
        if wants_json:
            return jsonify({"success": False, "message": msg, "needs_rejoin": True}), 400
        flash(msg, "warning")
        return redirect(url_for('join'))

    response_value = request.form.get(f'response-{question_id}')
    if response_value is None:
        msg = "No response value submitted."
        if wants_json:
            return jsonify({"success": False, "message": msg}), 400
        flash(msg, "warning")
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

    if wants_json:
        return jsonify({
            "success": True,
            "message": "Your response was submitted!",
            "response_value": response_value,
        })
    # Using flash for confirmation (non-JS fallback)
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


def broadcast_questions_changed(session_id: int):
    """Notify audience members in a session room that the set of active
    questions (or the session's own active state) has changed, so their page
    can update live instead of requiring a manual refresh."""
    with app.app_context():
        s = db.session.get(Session, session_id)
        active_ids = [q.id for q in s.questions if q.active] if s else []
        session_active = bool(s and s.active and not s.archived and not s.deleted)
    socketio.emit(
        'questions_changed',
        {
            'session_id': session_id,
            'active_question_ids': active_ids,
            'session_active': session_active,
        },
        room=f'session_{session_id}',
    )
    print(f"Emitted questions_changed for room session_{session_id}")


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


@socketio.on('join_session')
def handle_join_session(data):
    """Audience clients join a room scoped to the whole session so they get
    notified when the presenter activates/deactivates questions."""
    session_id = data.get('session_id')
    if session_id is not None:
        try:
            s_id = int(session_id)
            join_room(f'session_{s_id}')
            print(f"Client {request.sid} joined session room session_{s_id}")
        except (ValueError, TypeError):
            print(f"Invalid session_id received for join_session: {session_id}")


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
            # Use the configured password, or generate a strong random one and
            # surface it exactly once so it never ships as a known default.
            admin_pass = DEFAULT_ADMIN_PASS
            generated = False
            if not admin_pass:
                admin_pass = secrets.token_urlsafe(16)
                generated = True

            password_h = hash_password(admin_pass)
            if generated:
                print(
                    "\n" + "=" * 70 +
                    f"\nCreated admin user '{DEFAULT_ADMIN_USER}' with a GENERATED password:"
                    f"\n\n    {admin_pass}\n\n"
                    "Save it now and change it after first login. This is shown only once.\n"
                    "(Set DEFAULT_ADMIN_PASS in the environment to choose your own.)\n"
                    + "=" * 70 + "\n"
                )
            else:
                print(f"Creating admin user '{DEFAULT_ADMIN_USER}' from DEFAULT_ADMIN_PASS.")
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



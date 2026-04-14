"""
auth.py — Authentication module for CVEmbed AI
Handles: user registration, login, logout, JWT tokens, SQLite user DB, analysis history
"""

import sqlite3
import os
import bcrypt
import jwt
import datetime
import logging
import re
from flask import Blueprint, request, render_template, redirect, url_for, make_response

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# SQLite DB path (same folder as app.py)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.db')

# JWT secret — override via environment variable in production
SECRET_KEY = os.environ.get('SECRET_KEY', 'cv-embed-super-secret-hackathon-key-2025-change-in-prod')


def _db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    return conn


def _is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or ""))


def _safe_check_password(plain_password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            (plain_password or "").encode('utf-8'),
            (stored_hash or "").encode('utf-8'),
        )
    except Exception:
        logger.warning("Malformed password hash found for a user record.")
        return False


# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------

def init_db():
    """Create users and analysis_history tables if they don't exist."""
    try:
        with _db_conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    username        TEXT UNIQUE NOT NULL,
                    email           TEXT UNIQUE NOT NULL,
                    password_hash   TEXT NOT NULL,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id         INTEGER NOT NULL,
                    similarity_score REAL NOT NULL DEFAULT 0,
                    top_role        TEXT,
                    model_type      TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)')
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)')
            conn.commit()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# JWT Helpers
# ---------------------------------------------------------------------------

def get_current_user(req=None):
    """
    Decode JWT from the auth_token cookie.
    Returns the payload dict if valid, else None.
    """
    if req is None:
        req = request
    token = req.cookies.get('auth_token')
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("JWT token expired.")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"Invalid JWT token: {e}")
        return None


def _make_jwt(user_id, username, email):
    """Create a signed JWT token valid for 7 days."""
    payload = {
        'user_id': user_id,
        'username': username,
        'email': email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


# ---------------------------------------------------------------------------
# History Helpers
# ---------------------------------------------------------------------------

def save_analysis(user_id, similarity_score, top_role, model_type):
    """Persist an analysis result in the database for a logged-in user."""
    try:
        with _db_conn() as conn:
            conn.execute(
                'INSERT INTO analysis_history (user_id, similarity_score, top_role, model_type) VALUES (?, ?, ?, ?)',
                (user_id, round(float(similarity_score), 2), top_role or 'Unknown', model_type or 'unknown')
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to save analysis history: {e}", exc_info=True)


def get_user_history(user_id, limit=30):
    """Return list of past analysis dicts for the given user, newest first."""
    try:
        with _db_conn() as conn:
            rows = conn.execute(
                '''SELECT id, similarity_score, top_role, model_type, created_at
                   FROM analysis_history
                   WHERE user_id = ?
                   ORDER BY created_at DESC
                   LIMIT ?''',
                (user_id, limit)
            ).fetchall()
        return [
            {
                'id': r[0],
                'similarity_score': r[1],
                'top_role': r[2],
                'model_type': r[3],
                'created_at': r[4],
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Failed to retrieve history for user {user_id}: {e}", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Auth Routes
# ---------------------------------------------------------------------------

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page — validates credentials and issues JWT cookie."""
    # If already logged in, go home
    if get_current_user(request):
        return redirect(url_for('index'))

    registered = request.args.get('registered') == '1'
    success_msg = 'Account created! Please log in.' if registered else None

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            return render_template('login.html', error='Please fill in all fields.')
        if not _is_valid_email(email):
            return render_template('login.html', error='Please enter a valid email address.')
        if len(password) > 256:
            return render_template('login.html', error='Invalid password format.')

        try:
            with _db_conn() as conn:
                user = conn.execute(
                    'SELECT id, username, email, password_hash FROM users WHERE email = ?',
                    (email,)
                ).fetchone()
        except Exception as e:
            logger.error(f"DB error during login: {e}", exc_info=True)
            return render_template('login.html', error='A server error occurred. Please try again.')

        if user and _safe_check_password(password, user[3]):
            token = _make_jwt(user[0], user[1], user[2])
            resp = make_response(redirect(url_for('index')))
            resp.set_cookie(
                'auth_token', token,
                httponly=True,
                samesite='Lax',
                secure=os.environ.get('COOKIE_SECURE', '').lower() in ('1', 'true', 'yes'),
                max_age=7 * 24 * 3600
            )
            return resp

        return render_template('login.html', error='Invalid email or password. Please try again.')

    return render_template('login.html', success=success_msg)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page — creates a new user with bcrypt-hashed password."""
    if get_current_user(request):
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        # Validation
        if not username or not email or not password or not confirm:
            return render_template('register.html', error='All fields are required.')
        if len(username) < 3:
            return render_template('register.html', error='Username must be at least 3 characters.')
        if len(username) > 40:
            return render_template('register.html', error='Username is too long (max 40 characters).')
        if not re.match(r'^[A-Za-z0-9_.-]+$', username):
            return render_template('register.html', error='Username can only contain letters, numbers, _, ., and -')
        if not _is_valid_email(email):
            return render_template('register.html', error='Please enter a valid email address.')
        if len(password) < 8:
            return render_template('register.html', error='Password must be at least 8 characters.')
        if len(password) > 256:
            return render_template('register.html', error='Password is too long.')
        if password != confirm:
            return render_template('register.html', error='Passwords do not match.')

        # Hash and store
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        try:
            with _db_conn() as conn:
                conn.execute(
                    'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                    (username, email, password_hash)
                )
                conn.commit()
            return redirect(url_for('auth.login') + '?registered=1')
        except sqlite3.IntegrityError:
            return render_template('register.html', error='An account with this email or username already exists.')
        except Exception as e:
            logger.error(f"DB error during registration: {e}", exc_info=True)
            return render_template('register.html', error='A server error occurred. Please try again.')

    return render_template('register.html')


@auth_bp.route('/logout')
def logout():
    """Clear the auth cookie and redirect home."""
    resp = make_response(redirect(url_for('index')))
    resp.delete_cookie('auth_token')
    return resp

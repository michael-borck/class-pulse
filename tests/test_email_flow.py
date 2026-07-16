"""Email-verified registration and password-reset flows."""

from classpulse.extensions import db
from classpulse.models import EMAIL_CODE_RESET, EMAIL_CODE_VERIFY, EmailCode, User

from conftest import TEST_PASSWORD, create_user, login, make_app


def register(client, username, password="a-long-password", email=None):
    return client.post('/register', data={
        'username': username,
        'email': email or f"{username}@example.com",
        'display_name': username,
        'password': password,
        'confirm_password': password,
    }, follow_redirects=True)


def latest_code(app, email, purpose):
    """The newest unused code of `purpose` for the account, read straight from
    the DB (the dev email provider only logs, so this stands in for the inbox)."""
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        assert user is not None, f"no user for {email}"
        ec = (EmailCode.query
              .filter_by(user_id=user.id, purpose=purpose, used=False)
              .order_by(EmailCode.id.desc()).first())
        return ec.code if ec else None


# --- registration + verification -------------------------------------------

def test_second_registrant_verifies_by_email_then_logs_in(app, client):
    register(client, 'alice')                      # first user -> admin, verified
    register(client, 'bob')                        # needs email verification

    with app.app_context():
        bob = User.query.filter_by(username='bob').first()
        assert not bob.is_verified

    # Can't log in yet.
    resp = login(client, 'bob', 'a-long-password')
    assert b'not verified' in resp.data
    assert resp.request.path == '/login'

    # Verify with the emailed code.
    code = latest_code(app, 'bob@example.com', EMAIL_CODE_VERIFY)
    assert code and len(code) == 8
    resp = client.post('/verify-email', data={'email': 'bob@example.com', 'code': code},
                       follow_redirects=True)
    assert b'Email verified' in resp.data
    with app.app_context():
        assert User.query.filter_by(username='bob').first().is_verified

    # Now login works.
    resp = login(client, 'bob', 'a-long-password')
    assert b'Welcome back' in resp.data


def test_verify_rejects_wrong_and_reused_code(app, client):
    register(client, 'alice')
    register(client, 'bob')
    good = latest_code(app, 'bob@example.com', EMAIL_CODE_VERIFY)

    # Wrong code: stays unverified, generic error.
    resp = client.post('/verify-email', data={'email': 'bob@example.com', 'code': 'WRONGONE'},
                       follow_redirects=True)
    assert b'invalid or has expired' in resp.data
    with app.app_context():
        assert not User.query.filter_by(username='bob').first().is_verified

    # Correct code verifies.
    client.post('/verify-email', data={'email': 'bob@example.com', 'code': good},
                follow_redirects=True)
    # Reusing the same code fails (single-use).
    resp = client.post('/verify-email', data={'email': 'bob@example.com', 'code': good},
                       follow_redirects=True)
    assert b'invalid or has expired' in resp.data


def test_verify_rejects_expired_code(app, client):
    register(client, 'alice')
    register(client, 'bob')
    with app.app_context():
        bob = User.query.filter_by(username='bob').first()
        ec = (EmailCode.query.filter_by(user_id=bob.id, purpose=EMAIL_CODE_VERIFY, used=False)
              .order_by(EmailCode.id.desc()).first())
        code = ec.code
        ec.expires_at = EmailCode.expiry_iso(-1)  # already expired
        db.session.commit()

    resp = client.post('/verify-email', data={'email': 'bob@example.com', 'code': code},
                       follow_redirects=True)
    assert b'invalid or has expired' in resp.data
    with app.app_context():
        assert not User.query.filter_by(username='bob').first().is_verified


def test_resend_verification_issues_new_code(app, client):
    register(client, 'alice')
    register(client, 'bob')
    first = latest_code(app, 'bob@example.com', EMAIL_CODE_VERIFY)
    client.post('/resend-verification', data={'email': 'bob@example.com'},
                follow_redirects=True)
    second = latest_code(app, 'bob@example.com', EMAIL_CODE_VERIFY)
    assert second and second != first
    # The old code is retired; only the newest works.
    resp = client.post('/verify-email', data={'email': 'bob@example.com', 'code': first},
                       follow_redirects=True)
    assert b'invalid or has expired' in resp.data


# --- domain restriction -----------------------------------------------------

def test_registration_domain_lock():
    app = make_app({'ALLOWED_DOMAINS': ['curtin.edu.au']})
    client = app.test_client()
    try:
        resp = register(client, 'mallory', email='mallory@gmail.com')
        assert b'restricted to these email domains' in resp.data
        with app.app_context():
            assert User.query.filter_by(username='mallory').first() is None

        resp = register(client, 'grace', email='grace@curtin.edu.au')
        with app.app_context():
            assert User.query.filter_by(username='grace').first() is not None
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


# --- password reset ---------------------------------------------------------

def test_forgot_then_reset_password(app, client):
    create_user(app, 'alice')  # verified

    resp = client.post('/forgot-password', data={'email': 'alice@example.com'},
                       follow_redirects=True)
    assert b"sent it a code" in resp.data

    code = latest_code(app, 'alice@example.com', EMAIL_CODE_RESET)
    assert code and len(code) == 8

    new_password = "brand-new-password"
    resp = client.post('/reset-password', data={
        'email': 'alice@example.com', 'code': code,
        'password': new_password, 'confirm_password': new_password,
    }, follow_redirects=True)
    assert b'Password reset' in resp.data

    # Old password no longer works; new one does.
    assert b'Invalid username or password' in login(client, 'alice', TEST_PASSWORD).data
    assert b'Welcome back' in login(client, 'alice', new_password).data


def test_forgot_password_is_enumeration_safe(app, client):
    # Unknown email: same generic response, no error, no code created.
    resp = client.post('/forgot-password', data={'email': 'nobody@example.com'},
                       follow_redirects=True)
    assert b"sent it a code" in resp.data
    with app.app_context():
        assert EmailCode.query.count() == 0


def test_reset_rejects_short_password(app, client):
    create_user(app, 'alice')
    client.post('/forgot-password', data={'email': 'alice@example.com'})
    code = latest_code(app, 'alice@example.com', EMAIL_CODE_RESET)
    resp = client.post('/reset-password', data={
        'email': 'alice@example.com', 'code': code,
        'password': 'short', 'confirm_password': 'short',
    }, follow_redirects=True)
    assert b'at least 10 characters' in resp.data
    # Code not consumed (still valid for a real attempt).
    assert latest_code(app, 'alice@example.com', EMAIL_CODE_RESET) == code


def test_reset_rejects_reused_code(app, client):
    create_user(app, 'alice')
    client.post('/forgot-password', data={'email': 'alice@example.com'})
    code = latest_code(app, 'alice@example.com', EMAIL_CODE_RESET)
    data = {'email': 'alice@example.com', 'code': code,
            'password': 'first-new-password', 'confirm_password': 'first-new-password'}
    client.post('/reset-password', data=data, follow_redirects=True)
    # Reusing the consumed code fails.
    resp = client.post('/reset-password', data=data, follow_redirects=True)
    assert b'invalid or has expired' in resp.data


def test_password_reset_invalidates_other_sessions(app):
    create_user(app, 'alice')
    logged_in = app.test_client()
    attacker_free = app.test_client()

    # Session A logs in and can reach the dashboard.
    login(logged_in, 'alice')
    assert logged_in.get('/dashboard').status_code == 200

    # Alice resets her password from a fresh (logged-out) client.
    attacker_free.post('/forgot-password', data={'email': 'alice@example.com'})
    code = latest_code(app, 'alice@example.com', EMAIL_CODE_RESET)
    attacker_free.post('/reset-password', data={
        'email': 'alice@example.com', 'code': code,
        'password': 'rotated-password-x', 'confirm_password': 'rotated-password-x',
    })

    # Session A's cookie is now stale -> bounced to login.
    resp = logged_in.get('/dashboard')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']

import hashlib
import secrets

from classpulse.auth import PASSWORD_HASH_METHOD
from classpulse.extensions import db
from classpulse.models import User

from conftest import TEST_PASSWORD, create_user, login


def register(client, username, password="a-long-password", email=None):
    return client.post('/register', data={
        'username': username,
        'email': email or f"{username}@example.com",
        'display_name': username,
        'password': password,
        'confirm_password': password,
    }, follow_redirects=True)


def test_first_registrant_becomes_verified_admin(app, client):
    register(client, 'alice')
    with app.app_context():
        alice = User.query.filter_by(username='alice').first()
        assert alice is not None
        assert alice.is_admin and alice.is_verified


def test_second_registrant_is_unverified_and_cannot_login(app, client):
    register(client, 'alice')
    register(client, 'bob')
    with app.app_context():
        bob = User.query.filter_by(username='bob').first()
        assert not bob.is_admin and not bob.is_verified
    resp = login(client, 'bob', 'a-long-password')
    assert b'not verified' in resp.data
    assert resp.request.path == '/login'


def test_short_password_rejected(app, client):
    resp = register(client, 'alice', password='short')
    assert b'at least 10 characters' in resp.data
    with app.app_context():
        assert User.query.count() == 0


def test_login_and_logout(app, client):
    create_user(app, 'alice')
    resp = login(client, 'alice')
    assert b'Welcome back' in resp.data

    resp = client.post('/logout')
    assert resp.headers['Location'].endswith('/')

    resp = client.get('/')
    assert b'Turn any room into a' in resp.data   # the landing, not the login form
    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_wrong_password_rejected(app, client):
    create_user(app, 'alice')
    resp = login(client, 'alice', 'not-the-password')
    assert b'Invalid username or password' in resp.data


def test_unknown_user_rejected(app, client):
    resp = login(client, 'nobody')
    assert b'Invalid username or password' in resp.data


def test_dashboard_requires_login(client):
    resp = client.get('/dashboard')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_archived_user_cannot_login(app, client):
    uid = create_user(app, 'alice')
    with app.app_context():
        db.session.get(User, uid).is_archived = True
        db.session.commit()
    resp = login(client, 'alice')
    assert b'archived' in resp.data


def _legacy_hash(password: str) -> str:
    """The pre-upgrade format: '<salt hex>$<pbkdf2-sha256(100k) hex>'."""
    salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"{salt.hex()}${hashed.hex()}"


def test_legacy_password_hash_still_works_and_is_upgraded(app, client):
    with app.app_context():
        user = User(username='old-timer', email='old@example.com',
                    password_hash=_legacy_hash(TEST_PASSWORD), display_name='old',
                    is_admin=True, is_verified=True, is_archived=False)
        db.session.add(user)
        db.session.commit()
    resp = login(client, 'old-timer')
    assert b'Welcome back' in resp.data
    with app.app_context():
        stored = User.query.filter_by(username='old-timer').first().password_hash
        assert stored.startswith(PASSWORD_HASH_METHOD + '$')

"""Security headers, CSRF enforcement, rate limiting, CSV formula escaping."""

from classpulse.utils import csv_safe

from conftest import (
    add_response, create_question, create_session, create_user, login, make_app
)


def test_security_headers_present(app, client):
    resp = client.get('/join')
    assert resp.headers['X-Content-Type-Options'] == 'nosniff'
    assert resp.headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert 'Content-Security-Policy' in resp.headers
    assert "default-src 'self'" in resp.headers['Content-Security-Policy']
    assert resp.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'


def test_healthz(client):
    resp = client.get('/healthz')
    assert resp.status_code == 200 and resp.get_json()['status'] == 'ok'


def test_csrf_enforced_when_enabled():
    app = make_app({'WTF_CSRF_ENABLED': True})
    client = app.test_client()
    resp = client.post('/login', data={'username': 'x', 'password': 'y'})
    assert resp.status_code == 400  # missing CSRF token


def test_login_rate_limited():
    app = make_app({'RATELIMIT_ENABLED': True})
    client = app.test_client()
    statuses = [client.post('/login', data={'username': 'x', 'password': 'y'}).status_code
                for _ in range(12)]
    assert 429 in statuses


def test_csv_safe_neutralises_formulas():
    assert csv_safe('=HYPERLINK("http://evil")').startswith("'=")
    assert csv_safe('+1+1').startswith("'+")
    assert csv_safe('@SUM(A1)').startswith("'@")
    assert csv_safe('-2+3').startswith("'-")
    assert csv_safe('plain text') == 'plain text'
    assert csv_safe('') == ''


def test_export_escapes_formula_responses(app, client):
    alice = create_user(app, 'alice')
    sid = create_session(app, alice)
    qid = create_question(app, sid, q_type='short_answer', options=[])
    add_response(app, qid, sid, '=cmd|/C calc!A0', '00000000-0000-4000-8000-000000000000')
    login(client, 'alice')
    resp = client.get(f'/sessions/{sid}/export')
    assert resp.status_code == 200
    assert b"'=cmd" in resp.data
    assert b'\n=cmd' not in resp.data and b',=cmd' not in resp.data

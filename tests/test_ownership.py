from conftest import create_question, create_session, create_user, login


def test_cannot_view_another_users_session(app, client):
    alice = create_user(app, 'alice')
    create_user(app, 'bob')
    sid = create_session(app, alice)
    login(client, 'bob')
    assert client.get(f'/sessions/{sid}').status_code == 404
    assert client.get(f'/present/{sid}').status_code == 404
    assert client.get(f'/sessions/{sid}/export').status_code == 404


def test_cannot_modify_another_users_session_or_question(app, client):
    alice = create_user(app, 'alice')
    create_user(app, 'bob')
    sid = create_session(app, alice)
    qid = create_question(app, sid)
    login(client, 'bob')
    assert client.post(f'/api/sessions/{sid}/toggle').status_code == 404
    assert client.post(f'/api/sessions/{sid}/rename', json={'name': 'x'}).status_code == 404
    assert client.post(f'/api/sessions/{sid}/delete').status_code == 404
    assert client.post(f'/api/questions/{qid}/toggle').status_code == 403
    assert client.post(f'/api/questions/{qid}/edit',
                       json={'type': 'multiple_choice', 'title': 'x',
                             'options': 'a\nb'}).status_code == 403
    assert client.post(f'/api/questions/{qid}/delete').status_code == 403
    assert client.get(f'/questions/{qid}/results').status_code == 403
    assert client.get(f'/questions/{qid}/export').status_code == 403


def test_admin_endpoints_require_admin(app, client):
    create_user(app, 'admin', is_admin=True)
    bob = create_user(app, 'bob')
    login(client, 'bob')
    resp = client.get('/admin/users')
    assert resp.status_code == 302  # bounced to dashboard
    resp = client.post(f'/api/users/{bob}/toggle_verify', follow_redirects=False)
    assert resp.status_code == 302


def test_admin_can_toggle_verification(app, client):
    create_user(app, 'admin', is_admin=True)
    bob = create_user(app, 'bob', is_verified=False)
    login(client, 'admin')
    resp = client.post(f'/api/users/{bob}/toggle_verify')
    assert resp.status_code == 200
    assert resp.get_json()['verified'] is True


def test_admin_cannot_archive_self(app, client):
    admin = create_user(app, 'admin', is_admin=True)
    login(client, 'admin')
    resp = client.post(f'/api/users/{admin}/toggle_archive')
    assert resp.status_code == 400

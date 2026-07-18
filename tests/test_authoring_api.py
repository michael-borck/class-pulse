import json

from classpulse.extensions import db
from classpulse.models import Question, Session

from conftest import (
    add_response, create_question, create_session, create_user, login
)


def test_create_session_and_question(app, client):
    create_user(app, 'alice')
    login(client, 'alice')
    resp = client.post('/api/sessions', json={'name': 'Physics 101'})
    sid = resp.get_json()['session']['id']
    resp = client.post(f'/api/sessions/{sid}/questions', json={
        'type': 'multiple_choice', 'title': 'Pick', 'options': 'A\nB\nC'})
    body = resp.get_json()
    assert body['success'] and body['question']['options'] == ['A', 'B', 'C']


def test_question_payload_validation(app, client):
    alice = create_user(app, 'alice')
    sid = create_session(app, alice)
    login(client, 'alice')
    url = f'/api/sessions/{sid}/questions'
    assert client.post(url, json={'type': 'bogus', 'title': 'x'}).status_code == 400
    assert client.post(url, json={'type': 'multiple_choice', 'title': ''}).status_code == 400
    assert client.post(url, json={'type': 'multiple_choice', 'title': 'x',
                                  'options': 'only-one'}).status_code == 400
    assert client.post(url, json={'type': 'multiple_choice', 'title': 'x' * 300,
                                  'options': 'a\nb'}).status_code == 400


def test_structural_edit_blocked_once_responses_exist(app, client):
    alice = create_user(app, 'alice')
    sid = create_session(app, alice)
    qid = create_question(app, sid)
    add_response(app, qid, sid, 'Red', '00000000-0000-4000-8000-000000000000')
    login(client, 'alice')
    resp = client.post(f'/api/questions/{qid}/edit', json={
        'type': 'multiple_choice', 'title': 'New title', 'options': 'X\nY'})
    body = resp.get_json()
    assert body['partial'] and not body['success']
    with app.app_context():
        q = db.session.get(Question, qid)
        assert q.title == 'New title'
        assert json.loads(q.options) == ['Red', 'Green', 'Blue']  # unchanged


def test_archive_and_delete_return_json(app, client):
    alice = create_user(app, 'alice')
    sid = create_session(app, alice)
    login(client, 'alice')

    resp = client.post(f'/api/sessions/{sid}/archive')
    assert resp.status_code == 200 and resp.get_json()['archived'] is True
    resp = client.post(f'/api/sessions/{sid}/archive')
    assert resp.get_json()['archived'] is False

    resp = client.post(f'/api/sessions/{sid}/delete')
    body = resp.get_json()
    assert body['success'] is True
    with app.app_context():
        assert db.session.get(Session, sid) is None


def test_delete_with_responses_is_hard_and_cascades(app, client):
    """Results are disposable: deleting a session with responses removes it and
    its responses/questions outright, rather than moving it to a trash state."""
    from classpulse.models import Question, Response

    alice = create_user(app, 'alice')
    sid = create_session(app, alice)
    qid = create_question(app, sid)
    add_response(app, qid, sid, 'Red', '00000000-0000-4000-8000-000000000000')
    login(client, 'alice')

    resp = client.post(f'/api/sessions/{sid}/delete')
    assert resp.get_json()['success'] is True
    with app.app_context():
        assert db.session.get(Session, sid) is None
        assert Question.query.filter_by(session_id=sid).count() == 0
        assert Response.query.filter_by(session_id=sid).count() == 0


def test_question_delete_blocked_with_responses(app, client):
    alice = create_user(app, 'alice')
    sid = create_session(app, alice)
    qid = create_question(app, sid)
    add_response(app, qid, sid, 'Red', '00000000-0000-4000-8000-000000000000')
    login(client, 'alice')
    assert client.post(f'/api/questions/{qid}/delete').status_code == 400


def test_reorder(app, client):
    alice = create_user(app, 'alice')
    sid = create_session(app, alice)
    q1 = create_question(app, sid, title='one')
    q2 = create_question(app, sid, title='two')
    login(client, 'alice')
    client.post(f'/api/sessions/{sid}/questions/reorder', json={'order': [q2, q1]})
    resp = client.get(f'/api/sessions/{sid}/questions')
    titles = [q['title'] for q in resp.get_json()['questions']]
    assert titles == ['two', 'one']


def test_legacy_sessions_url_redirects_to_dashboard(app, client):
    create_user(app, 'alice')
    login(client, 'alice')
    resp = client.get('/sessions')
    assert resp.status_code == 302 and '/dashboard' in resp.headers['Location']

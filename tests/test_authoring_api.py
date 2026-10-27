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


def test_question_delete_with_responses_needs_confirmation(app, client):
    from classpulse.models import Response
    alice = create_user(app, 'alice')
    sid = create_session(app, alice)
    qid = create_question(app, sid)
    add_response(app, qid, sid, 'Red', '00000000-0000-4000-8000-000000000000')
    login(client, 'alice')
    first = client.post(f'/api/questions/{qid}/delete')
    assert first.status_code == 409
    assert first.get_json()['needs_confirm'] and first.get_json()['response_count'] == 1
    assert client.post(f'/api/questions/{qid}/delete', json={'force': True}).status_code == 200
    with app.app_context():
        assert db.session.get(Question, qid) is None
        assert Response.query.filter_by(question_id=qid).count() == 0


def test_deleting_a_question_from_an_approved_proposal(app, client):
    # The proposal keeps its history but no longer points at the question.
    from classpulse.models import Proposal
    alice = create_user(app, 'alice')
    sid = create_session(app, alice)
    qid = create_question(app, sid)
    with app.app_context():
        db.session.add(Proposal(session_id=sid, respondent_id='r1', type='short_answer',
                                title='Asked', status='approved', question_id=qid))
        db.session.commit()
    login(client, 'alice')
    assert client.post(f'/api/questions/{qid}/delete').status_code == 200
    with app.app_context():
        assert Proposal.query.first().question_id is None


def test_question_delete_blocked_in_archived_session(app, client):
    alice = create_user(app, 'alice')
    sid = create_session(app, alice, archived=True)
    qid = create_question(app, sid)
    login(client, 'alice')
    assert client.post(f'/api/questions/{qid}/delete', json={'force': True}).status_code == 400


def _upload(client, sid):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (40, 30), 'red').save(buf, 'PNG')
    buf.seek(0)
    resp = client.post(f'/api/sessions/{sid}/upload-image',
                       data={'image': (buf, 'red.png')}, content_type='multipart/form-data')
    return resp.get_json()['url']


def test_copy_question_to_another_session(app, client, tmp_path):
    app.config['UPLOAD_DIR'] = str(tmp_path)
    alice = create_user(app, 'alice')
    src = create_session(app, alice, code='SRC111')
    dst = create_session(app, alice, code='DST222', name='Next week')
    login(client, 'alice')
    url = _upload(client, src)
    q = client.post(f'/api/sessions/{src}/questions', json={
        'type': 'image_choice', 'title': 'Which?', 'options': f'Red|{url}\nOther|https://example.com/b.png',
        'answer': 'Red'}).get_json()['question']
    add_response(app, q['id'], src, 'Red', 'r1')

    resp = client.post(f'/api/questions/{q["id"]}/copy', json={'session_id': dst})
    body = resp.get_json()
    assert resp.status_code == 200 and body['session']['name'] == 'Next week'
    copy = body['question']
    assert copy['title'] == 'Which?' and copy['answer'] == {'correct': ['Red']}
    assert copy['response_count'] == 0
    # The uploaded image now has its own copy in the target session's folder;
    # the external URL is left alone.
    new_url = copy['options'][0]['url']
    assert new_url.startswith(f'/uploads/{dst}/') and new_url != url
    assert copy['options'][1]['url'] == 'https://example.com/b.png'
    assert client.get(new_url).status_code == 200
    client.post(f'/api/sessions/{src}/delete')
    assert client.get(new_url).status_code == 200  # survives the original's deletion


def test_copy_rules(app, client):
    alice = create_user(app, 'alice')
    src = create_session(app, alice, code='SRC111')
    archived = create_session(app, alice, code='ARC333', archived=True)
    qid = create_question(app, src)
    bob = create_user(app, 'bob')
    bobs = create_session(app, bob, code='BOB444')
    login(client, 'alice')
    assert client.post(f'/api/questions/{qid}/copy', json={'session_id': archived}).status_code == 400
    assert client.post(f'/api/questions/{qid}/copy', json={'session_id': bobs}).status_code == 404
    assert client.post(f'/api/questions/{qid}/copy', json={}).status_code == 400


def test_new_session_from_existing(app, client):
    alice = create_user(app, 'alice')
    src = create_session(app, alice, archived=True, name='Week 3')  # archived lessons can be reused
    q1 = create_question(app, src, title='one')
    create_question(app, src, title='two', active=False)
    add_response(app, q1, src, 'Red', 'r1')
    login(client, 'alice')
    body = client.post(f'/api/sessions/{src}/clone', json={}).get_json()
    new = body['session']
    assert body['success'] and new['name'] == 'Week 3 (copy)'
    assert new['active'] is False and new['archived'] is False and new['code']
    qs = client.get(f'/api/sessions/{new["id"]}/questions').get_json()['questions']
    assert [(q['title'], q['active'], q['response_count']) for q in qs] == [
        ('one', True, 0), ('two', False, 0)]
    named = client.post(f'/api/sessions/{src}/clone', json={'name': 'Class B'}).get_json()
    assert named['session']['name'] == 'Class B'


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

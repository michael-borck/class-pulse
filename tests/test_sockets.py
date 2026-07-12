"""Socket.IO room authorization: live results must not leak to strangers."""

from classpulse.extensions import socketio

from conftest import add_response, create_question, create_session, create_user, login


def _updates(received):
    return [r for r in received if r['name'] == 'update_results']


def test_stranger_can_watch_live_question(app, client):
    alice = create_user(app, 'alice')
    sid = create_session(app, alice, active=True)
    qid = create_question(app, sid)
    ws = socketio.test_client(app, flask_test_client=client)
    ws.emit('join', {'question_id': qid})
    assert _updates(ws.get_received())  # initial stats delivered


def test_stranger_cannot_watch_inactive_session(app, client):
    alice = create_user(app, 'alice')
    sid = create_session(app, alice, active=False)
    qid = create_question(app, sid)
    add_response(app, qid, sid, 'Red', '00000000-0000-4000-8000-000000000000')
    ws = socketio.test_client(app, flask_test_client=client)
    ws.emit('join', {'question_id': qid})
    assert not _updates(ws.get_received())


def test_stranger_cannot_watch_inactive_question(app, client):
    alice = create_user(app, 'alice')
    sid = create_session(app, alice, active=True)
    qid = create_question(app, sid, active=False)
    ws = socketio.test_client(app, flask_test_client=client)
    ws.emit('join', {'question_id': qid})
    assert not _updates(ws.get_received())


def test_owner_can_watch_inactive_session(app, client):
    alice = create_user(app, 'alice')
    sid = create_session(app, alice, active=False)
    qid = create_question(app, sid)
    login(client, 'alice')
    ws = socketio.test_client(app, flask_test_client=client)
    ws.emit('join', {'question_id': qid})
    assert _updates(ws.get_received())


def test_stranger_cannot_join_inactive_session_room(app, client):
    alice = create_user(app, 'alice')
    sid = create_session(app, alice, active=False)
    ws = socketio.test_client(app, flask_test_client=client)
    ws.emit('join_session', {'session_id': sid})
    # Toggling the session broadcasts to the room; a refused client hears nothing.
    login(client, 'alice')
    client.post(f'/api/sessions/{sid}/toggle')
    assert not [r for r in ws.get_received() if r['name'] == 'questions_changed']


def test_audience_receives_questions_changed(app, client):
    alice = create_user(app, 'alice')
    sid = create_session(app, alice, active=True)
    create_question(app, sid)
    ws = socketio.test_client(app, flask_test_client=client)
    ws.emit('join_session', {'session_id': sid})
    ws.get_received()
    login(client, 'alice')
    client.post(f'/api/sessions/{sid}/toggle')  # deactivate → broadcast
    events = [r for r in ws.get_received() if r['name'] == 'questions_changed']
    assert events and events[0]['args'][0]['session_active'] is False


def test_garbage_join_payloads_ignored(app, client):
    ws = socketio.test_client(app, flask_test_client=client)
    ws.emit('join', {'question_id': 'zzz'})
    ws.emit('join', {})
    ws.emit('join_session', {'session_id': [1, 2]})
    ws.emit('leave', {'question_id': None})
    assert ws.is_connected()

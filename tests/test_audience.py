
from classpulse.models import Response

from conftest import (
    create_question, create_session, create_user, join_session
)

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


def _respond(client, qid, value, **extra_form):
    data = {f'response-{qid}': value, **extra_form}
    return client.post(f'/audience/respond/{qid}', data=data, headers=AJAX)


def setup_live(app, **q_kwargs):
    alice = create_user(app, 'alice')
    sid = create_session(app, alice)
    qid = create_question(app, sid, **q_kwargs)
    return sid, qid


def test_join_with_valid_code_sets_respondent_cookie(app, client):
    setup_live(app)
    resp = join_session(client)
    assert resp.status_code == 302
    cookie = client.get_cookie('classpulse_respondent')
    assert cookie is not None and len(cookie.value) == 36


def test_join_rejects_bad_code_format(app, client):
    setup_live(app)
    resp = client.post('/join', data={'code': 'nope; DROP TABLE'}, follow_redirects=True)
    assert b'Invalid' in resp.data


def test_join_rejects_inactive_session(app, client):
    alice = create_user(app, 'alice')
    create_session(app, alice, active=False)
    resp = client.post('/join', data={'code': 'ABC123'}, follow_redirects=True)
    assert b'Invalid' in resp.data


def test_multiple_choice_response_recorded(app, client):
    sid, qid = setup_live(app)
    join_session(client)
    resp = _respond(client, qid, 'Red')
    assert resp.status_code == 200 and resp.get_json()['success']
    with app.app_context():
        assert Response.query.filter_by(question_id=qid).count() == 1


def test_multiple_choice_rejects_value_not_in_options(app, client):
    sid, qid = setup_live(app)
    join_session(client)
    resp = _respond(client, qid, '<script>alert(1)</script>')
    assert resp.status_code == 400
    with app.app_context():
        assert Response.query.count() == 0


def test_resubmission_updates_instead_of_duplicating(app, client):
    sid, qid = setup_live(app)
    join_session(client)
    _respond(client, qid, 'Red')
    _respond(client, qid, 'Blue')
    with app.app_context():
        rows = Response.query.filter_by(question_id=qid).all()
        assert len(rows) == 1 and rows[0].response_value == 'Blue'


def test_short_answer_length_cap(app, client):
    sid, qid = setup_live(app, q_type='short_answer', options=[])
    join_session(client)
    assert _respond(client, qid, 'x' * 2001).status_code == 400
    assert _respond(client, qid, 'a fine answer').status_code == 200


def test_word_cloud_length_cap(app, client):
    sid, qid = setup_live(app, q_type='word_cloud', options=[])
    join_session(client)
    assert _respond(client, qid, 'x' * 201).status_code == 400
    assert _respond(client, qid, 'sunshine').status_code == 200


def test_rating_bounds(app, client):
    sid, qid = setup_live(app, q_type='rating', options={'max_rating': 5})
    join_session(client)
    assert _respond(client, qid, '7').status_code == 400
    assert _respond(client, qid, '0').status_code == 400
    assert _respond(client, qid, 'abc').status_code == 400
    assert _respond(client, qid, '4').status_code == 200


def test_numeric_bounds(app, client):
    sid, qid = setup_live(app, q_type='numeric', options={'min': 0, 'max': 10})
    join_session(client)
    assert _respond(client, qid, '11').status_code == 400
    assert _respond(client, qid, '-1').status_code == 400
    assert _respond(client, qid, 'NaN.. not a number').status_code == 400
    assert _respond(client, qid, '7.5').status_code == 200


def test_multi_select_rejects_foreign_values(app, client):
    from werkzeug.datastructures import MultiDict
    sid, qid = setup_live(app, q_type='multi_select')
    join_session(client)
    resp = client.post(f'/audience/respond/{qid}',
                       data=MultiDict([(f'response-{qid}', 'Red'),
                                       (f'response-{qid}', 'Purple')]),
                       headers=AJAX)
    assert resp.status_code == 400


def test_other_answer_length_cap(app, client):
    sid, qid = setup_live(app, q_type='multiple_choice_other')
    join_session(client)
    resp = _respond(client, qid, '__other__', **{f'response-{qid}-other': 'y' * 501})
    assert resp.status_code == 400
    resp = _respond(client, qid, '__other__', **{f'response-{qid}-other': 'something else'})
    assert resp.status_code == 200


def test_inactive_question_returns_conflict(app, client):
    sid, qid = setup_live(app, active=False)
    join_session(client)
    resp = _respond(client, qid, 'Red')
    assert resp.status_code == 409
    assert resp.get_json()['inactive']


def test_forged_respondent_cookie_is_rejected(app, client):
    sid, qid = setup_live(app)
    client.set_cookie('classpulse_respondent', 'not-a-uuid')
    resp = _respond(client, qid, 'Red')
    assert resp.status_code == 400
    assert resp.get_json()['needs_rejoin']


def test_oversized_request_body_rejected(app, client):
    sid, qid = setup_live(app, q_type='short_answer', options=[])
    join_session(client)
    resp = client.post(f'/audience/respond/{qid}',
                       data={f'response-{qid}': 'x' * 300_000}, headers=AJAX)
    assert resp.status_code == 413


def test_audience_view_requires_cookie(app, client):
    setup_live(app)
    resp = client.get('/audience/ABC123')
    assert resp.status_code == 302  # bounced to /join for a cookie

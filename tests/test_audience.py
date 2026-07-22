
import uuid

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


def test_generated_codes_have_no_confusable_characters(app):
    from classpulse.utils import generate_session_code
    with app.app_context():
        codes = [generate_session_code() for _ in range(60)]
    assert not set(''.join(codes)) & set('OILU'), \
        "codes must not contain glyphs confusable with 0/1"


def test_join_accepts_confusable_substitutions(app, client):
    """A legacy code containing O must still be reachable by someone who
    reasonably types a zero instead (and vice versa)."""
    alice = create_user(app, 'alice')
    create_session(app, alice, active=True, code='7ZOSGE')
    for typed in ('7ZOSGE', '7Z0SGE', '7z0sge'):
        resp = client.post('/join', data={'code': typed})
        assert resp.status_code == 302, f"{typed} should reach the session"
        # Always canonicalised to the stored spelling.
        assert resp.headers['Location'].endswith('/audience/7ZOSGE')


def test_audience_view_accepts_confusable_substitutions(app, client):
    alice = create_user(app, 'alice')
    create_session(app, alice, active=True, code='7ZOSGE')
    client.post('/join', data={'code': '7ZOSGE'})  # picks up the respondent cookie
    # Both spellings of the URL land on the session rather than bouncing to /join.
    assert client.get('/audience/7Z0SGE').status_code == 200
    assert client.get('/audience/7ZOSGE').status_code == 200


def test_cold_visitor_to_join_link_lands_in_the_session(app, client):
    """A QR scan or shared link goes straight to /audience/<code> with no
    cookie yet. That must work, not bounce to the join form."""
    setup_live(app)
    resp = client.get('/audience/ABC123')
    assert resp.status_code == 200, "a first-time visitor must not be redirected"
    assert b'Could not identify you' not in resp.data
    assert client.get_cookie('classpulse_respondent') is not None


def test_cold_visitor_keeps_identity_across_requests(app, client):
    """The minted id must persist, or answers would de-duplicate wrongly."""
    setup_live(app)
    client.get('/audience/ABC123')
    first = client.get_cookie('classpulse_respondent').value
    client.get('/audience/ABC123')
    assert client.get_cookie('classpulse_respondent').value == first


def test_join_page_prefills_code_from_query_string(app, client):
    resp = client.get('/join?code=abc123')
    assert b'value="ABC123"' in resp.data


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


def test_audience_view_replaces_a_malformed_respondent_cookie(app, client):
    """A cold visitor is issued an id (see the join-link tests above), but a
    hand-crafted cookie must never be taken at face value."""
    setup_live(app)
    client.set_cookie('classpulse_respondent', 'not-a-uuid; DROP TABLE')
    resp = client.get('/audience/ABC123')
    assert resp.status_code == 200
    issued = client.get_cookie('classpulse_respondent').value
    assert issued != 'not-a-uuid; DROP TABLE'
    uuid.UUID(issued)  # raises if the server didn't mint a real UUID

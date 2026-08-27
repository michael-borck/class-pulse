"""Emoji, matrix, and scatter question types: authoring validation, audience
submission rules, stats aggregation, and present-mode serialization."""

import json

from classpulse.stats import get_question_stats

from conftest import (
    add_response, create_question, create_session, create_user, join_session, login
)

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


def _create_via_api(client, sid, payload):
    return client.post(f'/api/sessions/{sid}/questions',
                       json={'title': 'Q?', **payload})


# ---------- emoji ----------

def test_emoji_create_and_respond(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    login(client, 'alice')
    resp = _create_via_api(client, sid, {'type': 'emoji', 'options': '😀 🙂 😐 🙁 😢'})
    assert resp.status_code == 200, resp.get_json()
    qid = resp.get_json()['question']['id']
    assert resp.get_json()['question']['options'] == ['😀', '🙂', '😐', '🙁', '😢']

    join_session(client)
    r = client.post(f'/audience/respond/{qid}', data={f'response-{qid}': '😀'},
                    headers=AJAX)
    assert r.status_code == 200, r.get_json()
    with app.app_context():
        stats = get_question_stats(qid)
    assert stats['results'] == {'😀': 1, '🙂': 0, '😐': 0, '🙁': 0, '😢': 0}


def test_emoji_rejects_unlisted_choice(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    qid = create_question(app, sid, q_type='emoji', title='Mood?',
                          options=['👍', '🤷', '👎'])
    join_session(client)
    r = client.post(f'/audience/respond/{qid}', data={f'response-{qid}': '💀'},
                    headers=AJAX)
    assert r.status_code == 400


def test_emoji_requires_at_least_two(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    login(client, 'alice')
    resp = _create_via_api(client, sid, {'type': 'emoji', 'options': '😀'})
    assert resp.status_code == 400


def test_emoji_dedupes_repeated_glyphs(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    login(client, 'alice')
    resp = _create_via_api(client, sid, {'type': 'emoji', 'options': '👍 👍 👎'})
    assert resp.get_json()['question']['options'] == ['👍', '👎']


# ---------- matrix ----------

def test_matrix_create_and_respond(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    login(client, 'alice')
    resp = _create_via_api(client, sid, {
        'type': 'matrix', 'cols': 3, 'rows': 2,
        'x_label': 'Impact', 'y_label': 'Likelihood', 'y_high': 'High'})
    assert resp.status_code == 200, resp.get_json()
    q = resp.get_json()['question']
    assert q['options']['cols'] == 3 and q['options']['rows'] == 2
    qid = q['id']

    join_session(client)
    r = client.post(f'/audience/respond/{qid}', data={f'response-{qid}': '2,1'},
                    headers=AJAX)
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['response_label'] == 'column 2, row 1'
    with app.app_context():
        stats = get_question_stats(qid)
    assert stats['results']['2,1'] == 1
    assert stats['results']['1,2'] == 0
    assert stats['grid'] == {'cols': 3, 'rows': 2, 'x_label': 'Impact',
                             'y_label': 'Likelihood', 'y_high': 'High'}


def test_matrix_rejects_cell_outside_grid(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    qid = create_question(app, sid, q_type='matrix', title='Place it',
                          options={'cols': 2, 'rows': 2})
    join_session(client)
    for bad in ('3,1', '0,1', '1,9', 'not-a-cell', ''):
        r = client.post(f'/audience/respond/{qid}', data={f'response-{qid}': bad},
                        headers=AJAX)
        assert r.status_code == 400, f"{bad!r} should be rejected"


def test_matrix_dims_clamped_to_2_to_4(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    login(client, 'alice')
    resp = _create_via_api(client, sid, {'type': 'matrix', 'cols': 9, 'rows': 1})
    q = resp.get_json()['question']
    assert q['options']['cols'] == 4 and q['options']['rows'] == 2


# ---------- scatter ----------

def test_scatter_create_and_respond_with_dimensions(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    login(client, 'alice')
    resp = _create_via_api(client, sid, {
        'type': 'scatter', 'x_label': 'Price', 'y_label': 'Quality',
        'allow_color': True, 'allow_size': True})
    assert resp.status_code == 200, resp.get_json()
    qid = resp.get_json()['question']['id']

    join_session(client)
    r = client.post(f'/audience/respond/{qid}', data={
        f'response-{qid}-x': '73.4', f'response-{qid}-y': '21',
        f'response-{qid}-color': 'red', f'response-{qid}-size': 'lg'}, headers=AJAX)
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['response_label'] == '(73, 21) red lg'
    with app.app_context():
        stats = get_question_stats(qid)
    assert stats['points'] == [{'x': 73.4, 'y': 21.0, 'c': 'red', 's': 'lg'}]
    assert stats['config']['x_label'] == 'Price'
    assert stats['config']['allow_color'] is True


def test_scatter_without_dimensions_stores_plain_point(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    qid = create_question(app, sid, q_type='scatter', title='Predict',
                          options={'x_label': 'X'})
    join_session(client)
    # Colour/size fields are ignored when the dimension isn't enabled.
    r = client.post(f'/audience/respond/{qid}', data={
        f'response-{qid}-x': '50', f'response-{qid}-y': '50',
        f'response-{qid}-color': 'blue'}, headers=AJAX)
    assert r.status_code == 200, r.get_json()
    with app.app_context():
        stats = get_question_stats(qid)
    assert stats['points'] == [{'x': 50.0, 'y': 50.0}]


def test_scatter_rejects_missing_or_out_of_range_point(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    qid = create_question(app, sid, q_type='scatter', title='Predict', options={})
    join_session(client)
    assert client.post(f'/audience/respond/{qid}', data={}, headers=AJAX).status_code == 400
    r = client.post(f'/audience/respond/{qid}', data={
        f'response-{qid}-x': '150', f'response-{qid}-y': '50'}, headers=AJAX)
    assert r.status_code == 400


def test_scatter_rejects_unknown_colour_when_enabled(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    qid = create_question(app, sid, q_type='scatter', title='Predict',
                          options={'allow_color': True})
    join_session(client)
    r = client.post(f'/audience/respond/{qid}', data={
        f'response-{qid}-x': '10', f'response-{qid}-y': '10',
        f'response-{qid}-color': 'chartreuse'}, headers=AJAX)
    assert r.status_code == 400


# ---------- present mode / results page serialization ----------

def test_present_mode_carries_new_type_options(app, client):
    # Same regression class as test_present_mode_includes_image_urls: the
    # projected page renders these types client-side, so their option/config
    # JSON must ship inside the QUESTIONS array.
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    create_question(app, sid, q_type='emoji', title='Mood?', options=['😀', '😢'])
    create_question(app, sid, q_type='matrix', title='Risk',
                    options={'cols': 2, 'rows': 2, 'x_label': 'Impact'})
    create_question(app, sid, q_type='scatter', title='Predict',
                    options={'x_label': 'Price'})
    login(client, 'alice')
    resp = client.get(f'/present/{sid}')
    assert resp.status_code == 200
    # tojson may ASCII-escape non-ASCII glyphs; either spelling means the
    # emoji options reached the page's QUESTIONS array.
    assert ('😀'.encode() in resp.data
            or json.dumps('😀')[1:-1].encode() in resp.data)
    assert b'"cols": 2' in resp.data
    assert b'Impact' in resp.data
    assert b'Price' in resp.data


def test_question_results_pages_render_new_types(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    login(client, 'alice')
    cases = [
        ('emoji', ['😀', '😢'], '😀'),
        ('matrix', {'cols': 2, 'rows': 2}, '1,1'),
        ('scatter', {}, '{"x":10,"y":20}'),
    ]
    for q_type, options, value in cases:
        qid = create_question(app, sid, q_type=q_type, title=f'T {q_type}',
                              options=options)
        add_response(app, qid, sid, value, respondent_id='r1')
        resp = client.get(f'/questions/{qid}/results')
        assert resp.status_code == 200, q_type
        assert b'Cannot display results for this question type' not in resp.data

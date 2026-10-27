"""Pin on image, slider, points allocation, and the fixes to the numeric,
word cloud, "Other" and ranking question types (plus scatter end labels)."""

import json

from classpulse.stats import get_question_stats

from conftest import (
    add_response, create_question, create_session, create_user, join_session, login
)

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


def _presenter(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    login(client, 'alice')
    return sid


def _create(client, sid, payload):
    return client.post(f'/api/sessions/{sid}/questions', json={'title': 'Q?', **payload})


def _stats(app, qid):
    with app.app_context():
        return get_question_stats(qid)


# ---------- pin on image ----------

def test_image_pin_create_respond_and_stats(app, client):
    sid = _presenter(app, client)
    assert _create(client, sid, {'type': 'image_pin', 'image_url': 'javascript:alert(1)'}
                   ).status_code == 400
    qid = _create(client, sid, {'type': 'image_pin', 'image_url': '/uploads/1/map.jpg'}
                  ).get_json()['question']['id']
    join_session(client)
    ok = client.post(f'/audience/respond/{qid}', data={
        f'response-{qid}-x': '25', f'response-{qid}-y': '75'}, headers=AJAX)
    assert ok.status_code == 200
    bad = client.post(f'/audience/respond/{qid}', data={
        f'response-{qid}-x': '125', f'response-{qid}-y': '75'}, headers=AJAX)
    assert bad.status_code == 400
    stats = _stats(app, qid)
    assert stats['points'] == [{'x': 25.0, 'y': 75.0}]
    assert stats['config']['image_url'] == '/uploads/1/map.jpg'


# ---------- slider ----------

def test_slider_validation_and_stats(app, client):
    sid = _presenter(app, client)
    assert _create(client, sid, {'type': 'slider', 'min': 10, 'max': 1}).status_code == 400
    qid = _create(client, sid, {'type': 'slider', 'min': 1, 'max': 5, 'step': 1,
                                'low_label': 'Not at all', 'high_label': 'Completely'}
                  ).get_json()['question']['id']
    join_session(client)
    assert client.post(f'/audience/respond/{qid}', data={f'response-{qid}': ''},
                       headers=AJAX).status_code == 400  # never moved
    assert client.post(f'/audience/respond/{qid}', data={f'response-{qid}': '9'},
                       headers=AJAX).status_code == 400  # out of range
    assert client.post(f'/audience/respond/{qid}', data={f'response-{qid}': '4'},
                       headers=AJAX).status_code == 200
    add_response(app, qid, sid, '2', 'r2')
    stats = _stats(app, qid)
    assert stats['results'] == {'1': 0, '2': 1, '3': 0, '4': 1, '5': 0}  # one bar per step
    assert stats['average'] == 3.0 and stats['median'] == 3.0
    assert stats['config']['low_label'] == 'Not at all'


# ---------- points allocation ----------

def test_points_must_add_up_and_average(app, client):
    sid = _presenter(app, client)
    qid = _create(client, sid, {'type': 'points', 'options': 'Algebra\nGeometry\nStats',
                                'total': 100}).get_json()['question']['id']
    join_session(client)

    def send(a, b, c):
        return client.post(f'/audience/respond/{qid}', data={
            f'response-{qid}-0': a, f'response-{qid}-1': b, f'response-{qid}-2': c}, headers=AJAX)
    assert send('50', '30', '30').status_code == 400   # 110
    assert send('-10', '60', '50').status_code == 400  # negative
    r = send('50', '30', '20')
    assert r.status_code == 200
    assert r.get_json()['response_label'] == 'Algebra: 50, Geometry: 30, Stats: 20'
    add_response(app, qid, sid, json.dumps({'Algebra': 0, 'Geometry': 100, 'Stats': 0}), 'r2')
    stats = _stats(app, qid)
    assert stats['results'] == {'Algebra': 25.0, 'Geometry': 65.0, 'Stats': 10.0}
    assert stats['total'] == 100


# ---------- fixes to existing types ----------

def test_numeric_input_accepts_decimals_without_a_step(app, client):
    sid = _presenter(app, client)
    create_question(app, sid, q_type='numeric', options={'min': 0, 'max': 10})
    assert b'step="any"' in client.get('/audience/ABC123').data


def test_word_cloud_counts_whole_phrases(app, client):
    sid = _presenter(app, client)
    qid = create_question(app, sid, q_type='word_cloud', options={})
    for i, text in enumerate(['Machine learning', 'machine  learning!', 'AI', 'the']):
        add_response(app, qid, sid, text, f'r{i}')
    words = {w['text']: w['weight'] for w in _stats(app, qid)['results']}
    assert words == {'machine learning': 2, 'ai': 1}


def test_other_answers_are_listed(app, client):
    sid = _presenter(app, client)
    qid = create_question(app, sid, q_type='multiple_choice_other', options=['Red', 'Blue'])
    add_response(app, qid, sid, 'Red', 'r1')
    add_response(app, qid, sid, 'Teal', 'r2')
    stats = _stats(app, qid)
    assert stats['results']['Other'] == 1
    assert [a['text'] for a in stats['other_answers']] == ['Teal']


def test_ranking_scores_put_the_favourite_first(app, client):
    sid = _presenter(app, client)
    qid = create_question(app, sid, q_type='ranking', options=['A', 'B', 'C'])
    add_response(app, qid, sid, 'C\nA\nB', 'r1')
    add_response(app, qid, sid, 'C\nB\nA', 'r2')
    stats = _stats(app, qid)
    assert stats['options'][0] == 'C'
    assert stats['scores']['C'] == 3.0  # always 1st of 3


def test_ranking_page_uses_reorder_controls(app, client):
    sid = _presenter(app, client)
    create_question(app, sid, q_type='ranking', options=['A', 'B', 'C'])
    page = client.get('/audience/ABC123').data
    assert b'class="rk-list' in page and b'Move A up' in page
    assert b'<select' not in page


def test_scatter_end_labels_and_quadrants(app, client):
    sid = _presenter(app, client)
    qid = _create(client, sid, {'type': 'scatter', 'x_label': 'Price', 'x_low': 'Cheap',
                                'x_high': 'Expensive', 'quadrants': True}
                  ).get_json()['question']['id']
    cfg = _stats(app, qid)['config']
    assert cfg['x_low'] == 'Cheap' and cfg['x_high'] == 'Expensive' and cfg['quadrants'] is True
    page = client.get('/audience/ABC123').data
    assert b'Cheap' in page and b'Expensive' in page


def test_new_types_render_everywhere(app, client):
    sid = _presenter(app, client)
    cases = [
        ('image_pin', {'image_url': '/uploads/1/a.jpg'}, '{"x":10,"y":20}'),
        ('slider', {'min': 0, 'max': 100, 'step': 1}, '42'),
        ('points', {'items': ['A', 'B'], 'total': 10}, '{"A":4,"B":6}'),
    ]
    for q_type, options, value in cases:
        qid = create_question(app, sid, q_type=q_type, title=f'T {q_type}', options=options)
        add_response(app, qid, sid, value, respondent_id='r1')
        assert client.get(f'/questions/{qid}/results').status_code == 200, q_type
    assert client.get(f'/present/{sid}').status_code == 200
    assert client.get(f'/sessions/{sid}/results').status_code == 200
    assert client.get('/audience/ABC123').status_code == 200

def test_ranking_and_select_all_labels_read_as_lists():
    from classpulse.questions import response_display_label
    assert response_display_label('ranking', 'C\nA\nB') == '1. C, 2. A, 3. B'
    assert response_display_label('multi_select', 'A\nC') == 'A, C'

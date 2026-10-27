"""Quiz mode, pin on image, slider, points allocation, and the fixes to the
numeric, word cloud, "Other" and ranking question types."""

import json

from classpulse.extensions import db
from classpulse.models import Question
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


# ---------- quiz mode ----------

def test_quiz_answer_must_match_an_option(app, client):
    sid = _presenter(app, client)
    bad = _create(client, sid, {'type': 'multiple_choice', 'options': 'Paris\nLyon',
                                'answer': 'Marseille'})
    assert bad.status_code == 400 and 'isn' in bad.get_json()['message']
    two = _create(client, sid, {'type': 'multiple_choice', 'options': 'Paris\nLyon',
                                'answer': 'Paris\nLyon'})
    assert two.status_code == 400  # single-answer types take exactly one
    ok = _create(client, sid, {'type': 'multiple_choice', 'options': 'Paris\nLyon',
                               'answer': 'Paris'})
    assert ok.get_json()['question']['answer'] == {'correct': ['Paris']}


def test_quiz_scoring_and_reveal_closes_answers(app, client):
    sid = _presenter(app, client)
    q = _create(client, sid, {'type': 'multiple_choice', 'options': 'Paris\nLyon',
                              'answer': 'Paris'}).get_json()['question']
    qid = q['id']
    add_response(app, qid, sid, 'Paris', 'r1')
    add_response(app, qid, sid, 'Lyon', 'r2')
    quiz = _stats(app, qid)['quiz']
    assert quiz['correct_count'] == 1 and quiz['percent_correct'] == 50
    assert quiz['correct_labels'] == ['Paris'] and quiz['revealed'] is False

    assert client.post(f'/api/questions/{qid}/reveal').get_json()['revealed'] is True
    assert _stats(app, qid)['quiz']['revealed'] is True

    student = app.test_client()
    student.post('/join', data={'code': 'ABC123'})
    r = student.post(f'/audience/respond/{qid}', data={f'response-{qid}': 'Paris'}, headers=AJAX)
    assert r.status_code == 409 and 'revealed' in r.get_json()['message']


def test_revealed_quiz_tells_each_student_how_they_did(app, client):
    sid = _presenter(app, client)
    qid = _create(client, sid, {'type': 'multiple_choice', 'options': 'Paris\nLyon',
                                'answer': 'Paris'}).get_json()['question']['id']
    student = app.test_client()
    student.post('/join', data={'code': 'ABC123'})
    student.post(f'/audience/respond/{qid}', data={f'response-{qid}': 'Lyon'}, headers=AJAX)
    client.post(f'/api/questions/{qid}/reveal')
    page = student.get('/audience/ABC123').data
    assert b'Not this time. The answer is Paris' in page
    assert b'<fieldset disabled' in page


def test_multi_select_and_numeric_quiz_scoring(app, client):
    sid = _presenter(app, client)
    ms = _create(client, sid, {'type': 'multi_select', 'options': 'A\nB\nC',
                               'answer': 'A\nC'}).get_json()['question']['id']
    add_response(app, ms, sid, 'A\nC', 'r1')
    add_response(app, ms, sid, 'A', 'r2')  # partly right is wrong
    assert _stats(app, ms)['quiz']['correct_count'] == 1

    num = _create(client, sid, {'type': 'numeric', 'min': 0, 'max': 10,
                                'answer_value': 3.14, 'answer_tolerance': 0.01}
                  ).get_json()['question']['id']
    add_response(app, num, sid, '3.141', 'r1')
    add_response(app, num, sid, '3.2', 'r2')
    quiz = _stats(app, num)['quiz']
    assert quiz['correct_count'] == 1 and quiz['answer_text'] == '3.14 (±0.01)'
    assert quiz['correct_labels'] == ['3–4']


def test_answer_key_can_be_fixed_after_responses(app, client):
    sid = _presenter(app, client)
    qid = _create(client, sid, {'type': 'multiple_choice', 'options': 'Paris\nLyon',
                                'answer': 'Lyon'}).get_json()['question']['id']
    add_response(app, qid, sid, 'Paris', 'r1')
    client.post(f'/api/questions/{qid}/edit', json={
        'type': 'multiple_choice', 'title': 'Q?', 'options': 'Paris\nLyon', 'answer': 'Paris'})
    assert _stats(app, qid)['quiz']['correct_count'] == 1


def test_reveal_needs_an_answer_and_an_owner(app, client):
    sid = _presenter(app, client)
    plain = create_question(app, sid)
    assert client.post(f'/api/questions/{plain}/reveal').status_code == 400
    quiz = _create(client, sid, {'type': 'multiple_choice', 'options': 'A\nB',
                                 'answer': 'A'}).get_json()['question']['id']
    create_user(app, 'mallory')
    other = app.test_client()
    login(other, 'mallory')
    assert other.post(f'/api/questions/{quiz}/reveal').status_code == 403


def test_present_hides_quiz_until_revealed(app, client):
    sid = _presenter(app, client)
    _create(client, sid, {'type': 'multiple_choice', 'options': 'A\nB', 'answer': 'A'})
    page = client.get(f'/present/{sid}').data
    assert b'quiz: true, revealed: false' in page


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


def test_migration_adds_quiz_columns(tmp_path):
    import sqlite3
    from conftest import make_app
    db_path = tmp_path / 'old.db'
    make_app({'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}'})
    con = sqlite3.connect(db_path)
    con.execute('ALTER TABLE question DROP COLUMN answer')
    con.execute('ALTER TABLE question DROP COLUMN revealed')
    con.commit()
    con.close()
    app = make_app({'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}'})
    with app.app_context():
        cols = {c['name'] for c in db.inspect(db.engine).get_columns('question')}
        assert {'answer', 'revealed'} <= cols
        assert Question.query.count() == 0


def test_ranking_and_select_all_labels_read_as_lists():
    from classpulse.questions import response_display_label
    assert response_display_label('ranking', 'C\nA\nB') == '1. C, 2. A, 3. B'
    assert response_display_label('multi_select', 'A\nC') == 'A, C'

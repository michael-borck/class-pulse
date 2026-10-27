"""Fixes to the numeric, word cloud, "Other" and ranking question types,
and scatter end labels."""

from classpulse.stats import get_question_stats

from conftest import add_response, create_question, create_session, create_user, login

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

def test_ranking_and_select_all_labels_read_as_lists():
    from classpulse.questions import response_display_label
    assert response_display_label('ranking', 'C\nA\nB') == '1. C, 2. A, 3. B'
    assert response_display_label('multi_select', 'A\nC') == 'A, C'

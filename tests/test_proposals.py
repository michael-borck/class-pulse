"""Cohort mode: audience-proposed questions, voting, moderation, presenter actions."""

from classpulse import moderation
from classpulse.extensions import db
from classpulse.models import Session

from conftest import create_session, create_user, join_session, login


def setup_cohort(app, **kwargs):
    alice = create_user(app, 'alice')
    sid = create_session(app, alice, allow_proposals=True, **kwargs)
    return alice, sid


def propose(client, code='ABC123', title='Which topic should we revise?',
            q_type='short_answer', **extra):
    return client.post(f'/audience/{code}/proposals',
                       json={'type': q_type, 'title': title, **extra})


# ---------- audience: create + list ----------

def test_proposal_appears_in_public_list(app, client):
    setup_cohort(app)
    join_session(client)
    resp = propose(client)
    assert resp.status_code == 200 and resp.get_json()['success']
    assert resp.get_json()['proposal']['status'] == 'visible'
    listing = client.get('/audience/ABC123/proposals').get_json()
    assert listing['enabled'] and len(listing['proposals']) == 1
    assert listing['proposals'][0]['mine'] is True
    assert listing['remaining'] == 4


def test_proposals_disabled_returns_404(app, client):
    alice = create_user(app, 'alice')
    create_session(app, alice, allow_proposals=False)
    join_session(client)
    assert propose(client).status_code == 404
    assert client.get('/audience/ABC123/proposals').status_code == 404


def test_proposals_closed_for_inactive_session(app, client):
    setup_cohort(app)
    join_session(client)
    with app.app_context():
        s = Session.query.first()
        s.active = False
        db.session.commit()
    assert propose(client).status_code == 404


def test_proposal_requires_respondent_cookie(app, client):
    setup_cohort(app)
    resp = propose(client)  # never joined → no cookie
    assert resp.status_code == 400 and resp.get_json()['needs_rejoin']


def test_proposal_type_restrictions(app, client):
    setup_cohort(app)
    join_session(client)
    assert propose(client, q_type='image_choice').status_code == 400
    assert propose(client, q_type='bogus').status_code == 400
    ok = propose(client, q_type='multiple_choice', title='Best colour?', options='Red\nBlue')
    assert ok.status_code == 200


def test_proposal_validation_reuses_question_rules(app, client):
    setup_cohort(app)
    join_session(client)
    assert propose(client, title='').status_code == 400
    assert propose(client, q_type='multiple_choice', title='x',
                   options='only-one').status_code == 400
    assert propose(client, title='y' * 300).status_code == 400


def test_per_respondent_proposal_cap(app, client):
    setup_cohort(app)
    join_session(client)
    for i in range(5):
        assert propose(client, title=f'Distinct question number {i} about topic {i}'
                       ).status_code == 200
    assert propose(client, title='One question too many now').status_code == 429


# ---------- moderation ----------

def test_blocklisted_keyword_flags_proposal(app, client):
    setup_cohort(app)
    join_session(client)
    resp = propose(client, title='why is this class such bullshit')
    body = resp.get_json()
    assert body['success'] and body['proposal']['status'] == 'flagged'
    assert 'presenter approval' in body['message']
    # Hidden from the public list, but the submitter sees it as pending.
    listing = client.get('/audience/ABC123/proposals').get_json()
    assert listing['proposals'] == []
    assert len(listing['mine_hidden']) == 1


def test_leetspeak_keyword_still_flags(app, client):
    setup_cohort(app)
    join_session(client)
    resp = propose(client, title='this is bull5hit surely')
    assert resp.get_json()['proposal']['status'] == 'flagged'


def test_similar_proposal_gets_hint_but_stays_visible(app, client):
    setup_cohort(app)
    join_session(client)
    first = propose(client, title='What is the photosynthesis process?').get_json()
    second = propose(client, title='what is photosynthesis process').get_json()
    assert second['proposal']['status'] == 'visible'
    assert second['proposal']['similar_to_id'] == first['proposal']['id']


def test_llm_flag_path(app, client, monkeypatch):
    monkeypatch.setattr(moderation.ai, 'AI_ENABLED', True)
    monkeypatch.setattr(moderation.ai, 'call_ai', lambda prompt: {
        "success": True, "response": '{"ok": false, "reason": "nsfw"}'})
    setup_cohort(app)
    join_session(client)
    body = propose(client, title='an innocuous looking title').get_json()
    assert body['proposal']['status'] == 'flagged'
    assert 'AI check' in body['proposal']['flag_reason']


def test_llm_error_flags_for_review(app, client, monkeypatch):
    monkeypatch.setattr(moderation.ai, 'AI_ENABLED', True)
    monkeypatch.setattr(moderation.ai, 'call_ai',
                        lambda prompt: {"success": False, "error": "timeout"})
    setup_cohort(app)
    join_session(client)
    body = propose(client).get_json()
    assert body['proposal']['status'] == 'flagged'
    assert 'unavailable' in body['proposal']['flag_reason']


def test_llm_ok_stays_visible(app, client, monkeypatch):
    monkeypatch.setattr(moderation.ai, 'AI_ENABLED', True)
    monkeypatch.setattr(moderation.ai, 'call_ai', lambda prompt: {
        "success": True, "response": '{"ok": true, "reason": null}'})
    setup_cohort(app)
    join_session(client)
    assert propose(client).get_json()['proposal']['status'] == 'visible'


# ---------- voting ----------

def test_vote_toggles_and_is_unique_per_respondent(app, client):
    setup_cohort(app)
    join_session(client)
    pid = propose(client).get_json()['proposal']['id']
    r1 = client.post(f'/audience/proposals/{pid}/vote').get_json()
    assert r1['voted'] is True and r1['votes'] == 1
    r2 = client.post(f'/audience/proposals/{pid}/vote').get_json()
    assert r2['voted'] is False and r2['votes'] == 0


def test_cannot_vote_on_flagged_proposal(app, client):
    setup_cohort(app)
    join_session(client)
    pid = propose(client, title='utter bullshit question').get_json()['proposal']['id']
    assert client.post(f'/audience/proposals/{pid}/vote').status_code == 400


# ---------- presenter actions ----------

def test_presenter_toggle_and_list(app, client):
    alice = create_user(app, 'alice')
    sid = create_session(app, alice, allow_proposals=False)
    login(client, 'alice')
    resp = client.post(f'/api/sessions/{sid}/proposals/toggle')
    assert resp.get_json()['enabled'] is True
    listing = client.get(f'/api/sessions/{sid}/proposals').get_json()
    assert listing['enabled'] and listing['flagged'] == [] and listing['visible'] == []


def test_presenter_sees_flagged_with_reason(app, client):
    alice, sid = setup_cohort(app)
    join_session(client)
    propose(client, title='complete bullshit honestly')
    login(client, 'alice')
    listing = client.get(f'/api/sessions/{sid}/proposals').get_json()
    assert len(listing['flagged']) == 1
    assert 'keyword filter' in listing['flagged'][0]['flag_reason']


def test_unflag_publishes_to_audience(app, client):
    alice, sid = setup_cohort(app)
    join_session(client)
    pid = propose(client, title='total bullshit but actually fine'
                  ).get_json()['proposal']['id']
    login(client, 'alice')
    resp = client.post(f'/api/proposals/{pid}/unflag')
    assert resp.get_json()['proposal']['status'] == 'visible'
    listing = client.get('/audience/ABC123/proposals').get_json()
    assert len(listing['proposals']) == 1


def test_approve_converts_to_live_question(app, client):
    alice, sid = setup_cohort(app)
    join_session(client)
    pid = propose(client, q_type='multiple_choice', title='Best colour?',
                  options='Red\nBlue').get_json()['proposal']['id']
    login(client, 'alice')
    resp = client.post(f'/api/proposals/{pid}/approve').get_json()
    assert resp['success'] and resp['question']['type'] == 'multiple_choice'
    assert resp['question']['options'] == ['Red', 'Blue']
    assert resp['proposal']['status'] == 'approved'
    qs = client.get(f'/api/sessions/{sid}/questions').get_json()['questions']
    assert any(q['title'] == 'Best colour?' for q in qs)
    # double-approve is rejected
    assert client.post(f'/api/proposals/{pid}/approve').status_code == 400


def test_approve_with_presenter_edits(app, client):
    alice, sid = setup_cohort(app)
    join_session(client)
    pid = propose(client, title='roughly worded question').get_json()['proposal']['id']
    login(client, 'alice')
    resp = client.post(f'/api/proposals/{pid}/approve', json={
        'type': 'multiple_choice', 'title': 'Cleanly worded question?',
        'options': 'Yes\nNo'}).get_json()
    assert resp['question']['title'] == 'Cleanly worded question?'


def test_reject_hides_from_public_and_tells_owner(app, client):
    alice, sid = setup_cohort(app)
    join_session(client)
    pid = propose(client).get_json()['proposal']['id']
    login(client, 'alice')
    client.post(f'/api/proposals/{pid}/reject')
    listing = client.get('/audience/ABC123/proposals').get_json()
    assert listing['proposals'] == []
    assert listing['mine_hidden'][0]['status'] == 'rejected'


def test_other_presenter_cannot_moderate(app, client):
    alice, sid = setup_cohort(app)
    create_user(app, 'mallory')
    join_session(client)
    pid = propose(client).get_json()['proposal']['id']
    login(client, 'mallory')
    assert client.get(f'/api/sessions/{sid}/proposals').status_code == 404
    assert client.post(f'/api/proposals/{pid}/approve').status_code == 403
    assert client.post(f'/api/proposals/{pid}/reject').status_code == 403
    assert client.post(f'/api/sessions/{sid}/proposals/toggle').status_code == 404


# ---------- merge ----------

R1 = '00000000-0000-4000-8000-000000000001'
R2 = '00000000-0000-4000-8000-000000000002'


def add_vote(app, proposal_id, respondent_id):
    from classpulse.models import ProposalVote
    with app.app_context():
        db.session.add(ProposalVote(proposal_id=proposal_id, respondent_id=respondent_id))
        db.session.commit()


def vote_count(app, proposal_id):
    from classpulse.models import ProposalVote
    with app.app_context():
        return ProposalVote.query.filter_by(proposal_id=proposal_id).count()


def test_merge_transfers_votes_without_double_counting(app, client):
    alice, sid = setup_cohort(app)
    join_session(client)
    a = propose(client, title='How does recursion terminate?').get_json()['proposal']['id']
    b = propose(client, title='Completely different topic about databases'
                ).get_json()['proposal']['id']
    add_vote(app, a, R1)                 # R1 voted on the target already
    add_vote(app, b, R1)                 # ...and on the duplicate (must not double)
    add_vote(app, b, R2)                 # R2 only voted on the duplicate (must move)
    login(client, 'alice')
    resp = client.post(f'/api/proposals/{b}/merge', json={'into': a}).get_json()
    assert resp['success']
    assert resp['proposal']['status'] == 'merged'
    assert resp['proposal']['similar_to_id'] == a
    assert resp['target']['votes'] == 2  # R1 once + R2 moved across
    assert vote_count(app, b) == 0
    # merged proposal is gone from the public list; submitter sees why
    listing = client.get('/audience/ABC123/proposals').get_json()
    assert [p['id'] for p in listing['proposals']] == [a]
    assert listing['mine_hidden'][0]['status'] == 'merged'


def test_merge_defaults_to_similarity_hint(app, client):
    alice, sid = setup_cohort(app)
    join_session(client)
    first = propose(client, title='What is the photosynthesis process?'
                    ).get_json()['proposal']['id']
    second = propose(client, title='what is photosynthesis process'
                     ).get_json()['proposal']['id']
    login(client, 'alice')
    resp = client.post(f'/api/proposals/{second}/merge').get_json()  # no body
    assert resp['success'] and resp['proposal']['similar_to_id'] == first


def test_merge_validation(app, client):
    alice, sid = setup_cohort(app)
    create_session(app, alice, code='ZZZ999', allow_proposals=True)  # a second session
    join_session(client)
    a = propose(client, title='A perfectly reasonable question about sorting'
                ).get_json()['proposal']['id']
    b = propose(client, title='Another unrelated question about queues'
                ).get_json()['proposal']['id']
    join_session(client, code='ZZZ999')
    foreign = propose(client, code='ZZZ999', title='A question in another session'
                      ).get_json()['proposal']['id']
    login(client, 'alice')
    assert client.post(f'/api/proposals/{a}/merge', json={'into': a}).status_code == 400
    assert client.post(f'/api/proposals/{a}/merge').status_code == 400  # no hint, no body
    assert client.post(f'/api/proposals/{a}/merge',
                       json={'into': foreign}).status_code == 400  # cross-session
    client.post(f'/api/proposals/{b}/reject')
    assert client.post(f'/api/proposals/{a}/merge',
                       json={'into': b}).status_code == 400  # target not open


def test_merged_frees_the_respondent_cap(app, client):
    alice, sid = setup_cohort(app)
    join_session(client)
    ids = [propose(client, title=f'Distinct question number {i} about topic {i}'
                   ).get_json()['proposal']['id'] for i in range(5)]
    assert propose(client, title='Over the cap now').status_code == 429
    login(client, 'alice')
    client.post(f'/api/proposals/{ids[1]}/merge', json={'into': ids[0]})
    # back as the audience member: one slot freed
    resp = client.post('/audience/ABC123/proposals',
                       json={'type': 'short_answer', 'title': 'Fits again after merge'})
    assert resp.status_code == 200


def test_other_presenter_cannot_merge(app, client):
    alice, sid = setup_cohort(app)
    create_user(app, 'mallory')
    join_session(client)
    a = propose(client, title='First question about widgets').get_json()['proposal']['id']
    b = propose(client, title='Second question about sprockets').get_json()['proposal']['id']
    login(client, 'mallory')
    assert client.post(f'/api/proposals/{b}/merge', json={'into': a}).status_code == 403


def test_additive_migration_backfills_allow_proposals(app):
    # Simulate a pre-cohort database: drop the column, then re-run the migration.
    from classpulse import _apply_additive_migrations
    from sqlalchemy import inspect, text
    with app.app_context():
        db.session.execute(text('ALTER TABLE "session" DROP COLUMN allow_proposals'))
        db.session.commit()
        assert 'allow_proposals' not in {c['name'] for c in
                                         inspect(db.engine).get_columns('session')}
        _apply_additive_migrations(app)
        assert 'allow_proposals' in {c['name'] for c in
                                     inspect(db.engine).get_columns('session')}

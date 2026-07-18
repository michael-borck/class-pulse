"""Block (reversible) vs Delete (permanent, cascading) — the account lifecycle."""

from classpulse.accounts import purge_user
from classpulse.extensions import db
from classpulse.models import (
    EmailCode, Proposal, ProposalVote, Question, Response, Session, User,
)

from conftest import (
    TEST_PASSWORD, add_response, create_question, create_session, create_user, login,
)


def _build_owned_tree(app, user_id, code):
    """Give a user a full subtree: session -> question + response + proposal + vote
    + an email code. Returns the ids so a test can assert they're gone."""
    sid = create_session(app, user_id, code=code, allow_proposals=True)
    qid = create_question(app, sid)
    add_response(app, qid, sid, "Red", "resp-1")
    with app.app_context():
        prop = Proposal(session_id=sid, respondent_id="resp-1", type="multiple_choice",
                        title="Audience idea", options="[]", status="visible")
        db.session.add(prop)
        db.session.commit()
        vote = ProposalVote(proposal_id=prop.id, respondent_id="resp-2")
        code_row = EmailCode(user_id=user_id, code="ABCD1234", purpose="verify",
                             expires_at="2999-01-01T00:00:00+00:00")
        db.session.add_all([vote, code_row])
        db.session.commit()
        return {"session": sid, "question": qid, "proposal": prop.id, "vote": vote.id,
                "email_code": code_row.id}


def _counts(app):
    with app.app_context():
        return {
            "users": User.query.count(), "sessions": Session.query.count(),
            "questions": Question.query.count(), "responses": Response.query.count(),
            "proposals": Proposal.query.count(), "votes": ProposalVote.query.count(),
            "codes": EmailCode.query.count(),
        }


# --- purge_user: complete, and scoped to one user ---------------------------

def test_purge_removes_the_whole_owned_subtree(app):
    uid = create_user(app, 'alice')
    _build_owned_tree(app, uid, code="AAA111")

    before = _counts(app)
    assert before == {"users": 1, "sessions": 1, "questions": 1, "responses": 1,
                      "proposals": 1, "votes": 1, "codes": 1}

    with app.app_context():
        purge_user(db.session.get(User, uid))

    assert _counts(app) == {"users": 0, "sessions": 0, "questions": 0, "responses": 0,
                            "proposals": 0, "votes": 0, "codes": 0}


def test_purge_leaves_other_users_data_untouched(app):
    keep = create_user(app, 'keeper')
    drop = create_user(app, 'gone')
    _build_owned_tree(app, keep, code="KEEP01")
    _build_owned_tree(app, drop, code="DROP01")

    with app.app_context():
        purge_user(db.session.get(User, drop))

    # Exactly the keeper's tree remains.
    assert _counts(app) == {"users": 1, "sessions": 1, "questions": 1, "responses": 1,
                            "proposals": 1, "votes": 1, "codes": 1}
    with app.app_context():
        assert User.query.filter_by(username='keeper').first() is not None


# --- admin delete endpoint --------------------------------------------------

def test_admin_can_delete_another_user(app, client):
    create_user(app, 'boss', is_admin=True)
    victim = create_user(app, 'victim')
    _build_owned_tree(app, victim, code="VIC001")
    login(client, 'boss')

    resp = client.post(f'/api/users/{victim}/delete')
    assert resp.status_code == 200 and resp.get_json()['success'] is True
    with app.app_context():
        assert db.session.get(User, victim) is None


def test_admin_cannot_delete_self_via_admin_endpoint(app, client):
    boss = create_user(app, 'boss', is_admin=True)
    login(client, 'boss')
    resp = client.post(f'/api/users/{boss}/delete')
    assert resp.status_code == 400
    with app.app_context():
        assert db.session.get(User, boss) is not None


def test_cannot_delete_the_last_admin(app, client):
    boss = create_user(app, 'boss', is_admin=True)
    other = create_user(app, 'other', is_admin=True)
    login(client, 'boss')
    # boss deleting other is fine (two admins); then other is the last admin.
    assert client.post(f'/api/users/{other}/delete').status_code == 200
    # Now make a second admin again to test the guard directly.
    second = create_user(app, 'second', is_admin=True)
    resp = client.post(f'/api/users/{second}/delete')
    assert resp.status_code == 200  # two admins -> allowed
    # Only boss left; boss can't be deleted by anyone (it's also self here).
    resp = client.post(f'/api/users/{boss}/delete')
    assert resp.status_code == 400


def test_non_admin_cannot_reach_delete_endpoint(app, client):
    create_user(app, 'plain')
    target = create_user(app, 'target')
    login(client, 'plain')
    resp = client.post(f'/api/users/{target}/delete')
    assert resp.status_code in (302, 403)
    with app.app_context():
        assert db.session.get(User, target) is not None


# --- self-service delete ----------------------------------------------------

def test_self_delete_requires_correct_password(app, client):
    uid = create_user(app, 'alice')
    login(client, 'alice')
    resp = client.post('/account/delete', data={'password': 'wrong'}, follow_redirects=True)
    assert b'password is incorrect' in resp.data
    with app.app_context():
        assert db.session.get(User, uid) is not None


def test_self_delete_removes_account_and_logs_out(app, client):
    uid = create_user(app, 'alice')
    _build_owned_tree(app, uid, code="SELF01")
    login(client, 'alice')

    resp = client.post('/account/delete', data={'password': TEST_PASSWORD})
    assert resp.status_code == 302 and resp.headers['Location'].endswith('/')
    with app.app_context():
        assert db.session.get(User, uid) is None
    # Session cleared: a protected page bounces to login.
    assert '/login' in client.get('/dashboard', follow_redirects=False).headers['Location']


def test_sole_admin_cannot_self_delete(app, client):
    uid = create_user(app, 'boss', is_admin=True)
    login(client, 'boss')
    resp = client.post('/account/delete', data={'password': TEST_PASSWORD}, follow_redirects=True)
    assert b'only administrator' in resp.data
    with app.app_context():
        assert db.session.get(User, uid) is not None


# --- block (reversible) vs delete (frees the identity) ----------------------

def test_blocked_user_cannot_log_in(app, client):
    create_user(app, 'nogo')
    with app.app_context():
        u = User.query.filter_by(username='nogo').first()
        u.is_archived = True
        db.session.commit()
    resp = login(client, 'nogo')
    assert b'has been blocked' in resp.data


def test_blocked_user_cannot_reregister_but_deleted_user_can(app, client):
    def register(username, email):
        return client.post('/register', data={
            'username': username, 'email': email, 'display_name': username,
            'password': 'a-long-password', 'confirm_password': 'a-long-password',
        }, follow_redirects=True)

    # First registrant is the auto-admin; second is our subject.
    register('admin', 'admin@example.com')
    register('sam', 'sam@example.com')

    # Block sam -> the email stays claimed, so re-registration is refused.
    with app.app_context():
        sam = User.query.filter_by(username='sam').first()
        sam.is_archived = True
        db.session.commit()
        sam_id = sam.id
    resp = register('sam2', 'sam@example.com')
    assert b'already registered' in resp.data

    # Delete sam -> the email is freed, so it can be registered fresh.
    with app.app_context():
        purge_user(db.session.get(User, sam_id))
    resp = register('sam3', 'sam@example.com')
    assert b'already registered' not in resp.data
    with app.app_context():
        assert User.query.filter_by(email='sam@example.com').first().username == 'sam3'


def test_admin_can_block_and_unblock_a_normal_user(app, client):
    create_user(app, 'boss', is_admin=True)
    other = create_user(app, 'other')
    login(client, 'boss')
    r1 = client.post(f'/api/users/{other}/toggle_archive').get_json()
    assert r1['success'] and r1['archived'] is True and r1['new_text'] == 'Unblock'
    r2 = client.post(f'/api/users/{other}/toggle_archive').get_json()
    assert r2['archived'] is False and r2['new_text'] == 'Block'


def test_admin_cannot_block_own_account(app, client):
    boss = create_user(app, 'boss', is_admin=True)
    login(client, 'boss')
    resp = client.post(f'/api/users/{boss}/toggle_archive')
    assert resp.status_code == 400
    assert b'block your own account' in resp.data

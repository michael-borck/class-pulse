import json

import pytest

from classpulse import create_app
from classpulse.auth import hash_password
from classpulse.extensions import db
from classpulse.models import Question, Response, Session, User

TEST_PASSWORD = "correct-horse-battery"


def make_app(extra_config=None):
    config = {
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key',
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',  # in-memory, StaticPool
        'WTF_CSRF_ENABLED': False,
        'RATELIMIT_ENABLED': False,
    }
    if extra_config:
        config.update(extra_config)
    return create_app(config)


@pytest.fixture()
def app():
    app = make_app()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def create_user(app, username, *, is_admin=False, is_verified=True, password=TEST_PASSWORD):
    with app.app_context():
        user = User(username=username, email=f"{username}@example.com",
                    password_hash=hash_password(password), display_name=username,
                    is_admin=is_admin, is_verified=is_verified, is_archived=False)
        db.session.add(user)
        db.session.commit()
        return user.id


def login(client, username, password=TEST_PASSWORD):
    return client.post('/login', data={'username': username, 'password': password},
                       follow_redirects=True)


def create_session(app, user_id, *, active=True, archived=False, deleted=False,
                   code="ABC123", name="Test session", allow_proposals=False):
    with app.app_context():
        s = Session(name=name, code=code, user_id=user_id, active=active,
                    archived=archived, deleted=deleted, allow_proposals=allow_proposals)
        db.session.add(s)
        db.session.commit()
        return s.id


def create_question(app, session_id, *, q_type='multiple_choice',
                    title='Pick one', options=("Red", "Green", "Blue"), active=True):
    with app.app_context():
        if isinstance(options, (list, tuple)):
            options_json = json.dumps(list(options))
        else:
            options_json = json.dumps(options)
        q = Question(session_id=session_id, type=q_type, title=title,
                     options=options_json, active=active)
        db.session.add(q)
        db.session.commit()
        return q.id


def add_response(app, question_id, session_id, value, respondent_id):
    with app.app_context():
        db.session.add(Response(question_id=question_id, session_id=session_id,
                                response_value=value, respondent_id=respondent_id))
        db.session.commit()


def join_session(client, code="ABC123"):
    """POST /join so the client picks up a respondent cookie."""
    return client.post('/join', data={'code': code})

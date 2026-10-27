"""Socket.IO handlers and result broadcasts.

Handlers are registered at import time on the shared `socketio` instance (not
inside create_app) so repeated factory calls — e.g. in tests — don't register
duplicates.

Authorization. IDs are sequential integers, so every room checks who's asking:
  - question_<id> rooms stream live results, including verbatim short answers.
    Only the session's owner may join (Present mode and the Results views).
  - session_<id> rooms carry "the question list changed" nudges. The owner may
    join, and so may an audience member who loaded the session's page with its
    code (see utils.mark_session_joined) while it is live.
Socket events skip Flask's before_request hooks, so _is_owner repeats the
login checks itself: a cookie revoked by a password reset, or belonging to a
blocked account, gets nothing.
"""

from flask import current_app, request, session as http_session

from .extensions import db, socketio
from .models import Question, Session, User
from .stats import get_question_stats
from .utils import has_joined_session
from flask_socketio import emit, join_room


def _is_owner(db_session) -> bool:
    uid = http_session.get('user_id')
    if uid is None or db_session.user_id != uid:
        return False
    user = db.session.get(User, uid)
    return (user is not None and not user.is_archived
            and http_session.get('session_token') == user.session_token)


def broadcast_results(question_id: int):
    """Fetches latest stats and emits them to the question's room."""
    stats = get_question_stats(question_id)
    room_name = f'question_{question_id}'
    socketio.emit('update_results', {'question_id': question_id, 'stats': stats}, room=room_name)
    current_app.logger.debug(f"Emitted update_results for room {room_name}")


def broadcast_proposals_changed(session_id: int):
    """Nudge everyone in the session room (audience + presenter dashboard) to
    re-fetch the proposal list. Payload is just the session id — clients pull
    the list over HTTP so visibility rules stay server-side."""
    socketio.emit('proposals_changed', {'session_id': session_id},
                  room=f'session_{session_id}')


def broadcast_questions_changed(session_id: int, edited_question_id: int = None):
    """Notify audience members in a session room that the set of active
    questions (or the session's own active state) has changed, so their page
    can update live instead of requiring a manual refresh.

    An edit leaves the active-id set unchanged, so `edited_question_id` names
    the question whose title/options changed; clients showing it reload it."""
    s = db.session.get(Session, session_id)
    active_ids = [q.id for q in s.questions if q.active] if s else []
    session_active = bool(s and s.is_live)
    payload = {
        'session_id': session_id,
        'active_question_ids': active_ids,
        'session_active': session_active,
    }
    if edited_question_id is not None:
        payload['edited_question_id'] = edited_question_id
    socketio.emit('questions_changed', payload, room=f'session_{session_id}')
    current_app.logger.debug(f"Emitted questions_changed for room session_{session_id}")


@socketio.on('connect')
def handle_connect():
    current_app.logger.debug(f"Client connected: {request.sid}")


@socketio.on('disconnect')
def handle_disconnect():
    current_app.logger.debug(f"Client disconnected: {request.sid}")


@socketio.on('join')
def handle_join_room(data):
    """Client requests to join a room for a specific question."""
    if not isinstance(data, dict):
        return
    question_id = data.get('question_id')
    if question_id is None:
        return
    try:
        q_id = int(question_id)
    except (ValueError, TypeError):
        current_app.logger.warning(f"Invalid question_id received for join: {question_id!r}")
        return
    question = db.session.get(Question, q_id)
    if question is None or not _is_owner(question.session):
        current_app.logger.info(f"Refused join to question_{q_id} for {request.sid}")
        return
    room_name = f'question_{q_id}'
    join_room(room_name)
    # Send current results immediately to the joining client only.
    stats = get_question_stats(q_id)
    emit('update_results', {'question_id': q_id, 'stats': stats}, room=request.sid)


@socketio.on('join_session')
def handle_join_session(data):
    """Audience clients join a room scoped to the whole session so they get
    notified when the presenter activates/deactivates questions."""
    if not isinstance(data, dict):
        return
    session_id = data.get('session_id')
    if session_id is None:
        return
    try:
        s_id = int(session_id)
    except (ValueError, TypeError):
        current_app.logger.warning(f"Invalid session_id received for join_session: {session_id!r}")
        return
    s = db.session.get(Session, s_id)
    if s is None or not (_is_owner(s) or (s.is_live and has_joined_session(s.id))):
        current_app.logger.info(f"Refused join to session_{s_id} for {request.sid}")
        return
    join_room(f'session_{s_id}')

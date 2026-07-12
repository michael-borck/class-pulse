"""Socket.IO handlers and result broadcasts.

Handlers are registered at import time on the shared `socketio` instance (not
inside create_app) so repeated factory calls — e.g. in tests — don't register
duplicates.

Authorization: question/session rooms carry live results, including verbatim
short-answer text, so a client may only join a room if the content is publicly
live (active question in an active, visible session) or the client is the
authenticated owner. IDs are sequential integers — without this check anyone
could enumerate and stream every session's results.
"""

from flask import current_app, request, session as http_session

from .extensions import db, socketio
from .models import Question, Session
from .stats import get_question_stats
from flask_socketio import emit, join_room, leave_room


def _is_owner(db_session) -> bool:
    uid = http_session.get('user_id')
    return uid is not None and db_session.user_id == uid


def _can_watch_question(question) -> bool:
    if question is None:
        return False
    s = question.session
    return _is_owner(s) or (question.active and s.is_live)


def broadcast_results(question_id: int):
    """Fetches latest stats and emits them to the question's room."""
    stats = get_question_stats(question_id)
    room_name = f'question_{question_id}'
    socketio.emit('update_results', {'question_id': question_id, 'stats': stats}, room=room_name)
    current_app.logger.debug(f"Emitted update_results for room {room_name}")


def broadcast_questions_changed(session_id: int):
    """Notify audience members in a session room that the set of active
    questions (or the session's own active state) has changed, so their page
    can update live instead of requiring a manual refresh."""
    s = db.session.get(Session, session_id)
    active_ids = [q.id for q in s.questions if q.active] if s else []
    session_active = bool(s and s.is_live)
    socketio.emit(
        'questions_changed',
        {
            'session_id': session_id,
            'active_question_ids': active_ids,
            'session_active': session_active,
        },
        room=f'session_{session_id}',
    )
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
    question_id = (data or {}).get('question_id')
    if question_id is None:
        return
    try:
        q_id = int(question_id)
    except (ValueError, TypeError):
        current_app.logger.warning(f"Invalid question_id received for join: {question_id!r}")
        return
    question = db.session.get(Question, q_id)
    if not _can_watch_question(question):
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
    session_id = (data or {}).get('session_id')
    if session_id is None:
        return
    try:
        s_id = int(session_id)
    except (ValueError, TypeError):
        current_app.logger.warning(f"Invalid session_id received for join_session: {session_id!r}")
        return
    s = db.session.get(Session, s_id)
    if s is None or not (_is_owner(s) or s.is_live):
        current_app.logger.info(f"Refused join to session_{s_id} for {request.sid}")
        return
    join_room(f'session_{s_id}')


@socketio.on('leave')
def handle_leave_room(data):
    """Client requests to leave a room."""
    question_id = (data or {}).get('question_id')
    if question_id is None:
        return
    try:
        q_id = int(question_id)
    except (ValueError, TypeError):
        return
    leave_room(f'question_{q_id}')

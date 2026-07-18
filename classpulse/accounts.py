"""Permanent account deletion.

ClassPulse treats survey data as disposable — there is no recovery use-case and
no retention requirement — so deleting a user really removes everything they own
rather than hiding it. This is the counterpart to the reversible *block* state
(the is_archived flag), which exists to keep a specific person out, not to tidy
up. See [[surface-email-send-failures]] context in auth.py for the block path.
"""

from .extensions import db
from .models import (
    EmailCode, Proposal, ProposalVote, Question, Response, Session, User,
)


def _delete_session_rows(session_id):
    """Delete a session's children and the session row itself. No commit, no
    file cleanup — the caller owns both. Children go before parents so it holds
    up even if SQLite foreign-key enforcement is on.
    """
    proposal_ids = [p.id for p in Proposal.query.filter_by(session_id=session_id).all()]
    if proposal_ids:
        (ProposalVote.query
         .filter(ProposalVote.proposal_id.in_(proposal_ids))
         .delete(synchronize_session=False))
    Proposal.query.filter_by(session_id=session_id).delete(synchronize_session=False)
    Response.query.filter_by(session_id=session_id).delete(synchronize_session=False)
    Question.query.filter_by(session_id=session_id).delete(synchronize_session=False)
    Session.query.filter_by(id=session_id).delete(synchronize_session=False)


def purge_session(session_id):
    """Permanently delete one session and everything it holds. Irreversible.

    Survey data is disposable here (no recovery use-case), so a deleted session
    and its responses are really gone rather than hidden. Uploaded image files
    are cleared best-effort *after* the DB commit, so a filesystem hiccup can't
    roll back the deletion.
    """
    from .uploads import delete_session_uploads  # lazy: see purge_user

    _delete_session_rows(session_id)
    db.session.commit()
    delete_session_uploads(session_id)


def purge_user(user):
    """Permanently delete `user` and every record they own. Irreversible."""
    # Imported lazily: uploads.py imports auth, which imports this module, so a
    # top-level import here would close a circular chain at startup.
    from .uploads import delete_session_uploads

    user_id = user.id
    session_ids = [s.id for s in Session.query.filter_by(user_id=user_id).all()]

    for sid in session_ids:
        _delete_session_rows(sid)
    EmailCode.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    # Delete by query rather than db.session.delete(user): the bulk deletes above
    # leave the identity map out of sync, and a plain relationship (no cascade)
    # would otherwise try to NULL the FK on rows we've already removed.
    User.query.filter_by(id=user_id).delete(synchronize_session=False)
    db.session.commit()

    for sid in session_ids:
        delete_session_uploads(sid)


def is_last_admin(user) -> bool:
    """True if deleting/blocking this admin would leave the app with none.

    Matters because registration hands admin to the first person to sign up
    when no admin exists — so an adminless deployment silently promotes the
    next registrant.
    """
    return bool(user.is_admin) and User.query.filter_by(is_admin=True).count() <= 1

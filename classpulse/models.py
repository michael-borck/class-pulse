import uuid
from datetime import datetime, timedelta, timezone

from .extensions import db


def utcnow_iso() -> str:
    """Current UTC time as a timezone-aware ISO-8601 string.

    Timestamps are stored as ISO strings (a legacy of the original schema);
    lexicographic order matches chronological order, which the queries rely on.
    """
    return datetime.now(timezone.utc).isoformat()


def new_session_token() -> str:
    """A fresh opaque token used to invalidate a user's existing logins.

    Stamped into the Flask session at login and re-checked on each request;
    rotating it (e.g. on password reset) logs the user out everywhere.
    """
    return uuid.uuid4().hex


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    display_name = db.Column(db.String(100))
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    # is_verified doubles as the "email confirmed" gate: a user can't log in
    # until it's true. The bootstrap admin and manually-verified users are
    # exempt from needing an email round-trip (see auth.py).
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    # Bumped on password reset to invalidate signed-cookie sessions on other
    # devices. Nullable + server_default so the additive migration can backfill
    # existing rows; login tolerates a NULL token (see auth.py/login).
    session_token = db.Column(db.String(32), nullable=True)
    sessions = db.relationship('Session', backref='creator', lazy=True)


class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.String, default=utcnow_iso)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    archived = db.Column(db.Boolean, default=False, nullable=False)
    deleted = db.Column(db.Boolean, default=False, nullable=False)  # soft delete
    # Cohort mode: audience members may propose questions (see proposals.py).
    # server_default so the additive migration in create_app can backfill.
    allow_proposals = db.Column(db.Boolean, default=False, nullable=False, server_default='0')
    questions = db.relationship('Question', backref='session', lazy=True,
                                order_by='Question.order, Question.created_at')
    responses = db.relationship('Response', backref='session', lazy=True)
    proposals = db.relationship('Proposal', backref='session', lazy=True)

    @property
    def is_live(self) -> bool:
        """Visible/joinable by the audience."""
        return self.active and not self.archived and not self.deleted


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # see VALID_QUESTION_TYPES
    title = db.Column(db.String(255), nullable=False)
    options = db.Column(db.Text, default='{}')  # JSON string for options/config
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.String, default=utcnow_iso)
    order = db.Column(db.Integer, default=0)
    responses = db.relationship('Response', backref='question', lazy=True)


class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)
    response_value = db.Column(db.Text, nullable=False)
    respondent_id = db.Column(db.String(36), nullable=False)  # anonymous UUID
    created_at = db.Column(db.String, default=utcnow_iso)


# Statuses a Proposal moves through. Flagged proposals are hidden from the
# public list until the presenter approves ("unflags") or rejects them.
# 'merged' means folded into another proposal (similar_to_id points at it);
# its votes were transferred across.
PROPOSAL_STATUSES = ('visible', 'flagged', 'approved', 'rejected', 'merged')


class Proposal(db.Model):
    """An audience-proposed question (cohort mode), pending presenter action."""
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)
    respondent_id = db.Column(db.String(36), nullable=False)  # anonymous UUID
    type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    options = db.Column(db.Text, default='[]')  # JSON, same shape as Question.options
    status = db.Column(db.String(20), default='visible', nullable=False)
    flag_reason = db.Column(db.String(200))  # why moderation flagged it (shown to presenter)
    similar_to_id = db.Column(db.Integer, db.ForeignKey('proposal.id'))  # near-duplicate hint
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'))  # set on approval
    created_at = db.Column(db.String, default=utcnow_iso)
    votes = db.relationship('ProposalVote', backref='proposal', lazy=True,
                            cascade='all, delete-orphan')


class ProposalVote(db.Model):
    """One anonymous upvote per respondent per proposal."""
    id = db.Column(db.Integer, primary_key=True)
    proposal_id = db.Column(db.Integer, db.ForeignKey('proposal.id'), nullable=False)
    respondent_id = db.Column(db.String(36), nullable=False)
    created_at = db.Column(db.String, default=utcnow_iso)
    __table_args__ = (db.UniqueConstraint('proposal_id', 'respondent_id',
                                          name='uq_vote_proposal_respondent'),)


# Purposes an EmailCode can serve.
EMAIL_CODE_VERIFY = 'verify'   # confirm a new registration's email
EMAIL_CODE_RESET = 'reset'     # authorise a password reset
EMAIL_CODE_PURPOSES = (EMAIL_CODE_VERIFY, EMAIL_CODE_RESET)


class EmailCode(db.Model):
    """A single-use, time-limited code emailed for verification or reset.

    One table serves both flows (distinguished by `purpose`). Codes are stored
    verbatim (not hashed): they're short-lived, single-use, rate-limited, and
    tied to a specific user_id, so the value of hashing them is marginal.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    code = db.Column(db.String(16), nullable=False)
    purpose = db.Column(db.String(16), nullable=False)  # see EMAIL_CODE_PURPOSES
    created_at = db.Column(db.String, default=utcnow_iso)
    expires_at = db.Column(db.String, nullable=False)  # ISO-8601 UTC
    used = db.Column(db.Boolean, default=False, nullable=False)
    user = db.relationship('User', lazy=True)

    @staticmethod
    def expiry_iso(ttl_minutes: int) -> str:
        """ISO timestamp `ttl_minutes` from now, matching utcnow_iso() format."""
        return (datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).isoformat()

    @property
    def is_expired(self) -> bool:
        return datetime.fromisoformat(self.expires_at) < datetime.now(timezone.utc)

    @property
    def is_valid(self) -> bool:
        return not self.used and not self.is_expired

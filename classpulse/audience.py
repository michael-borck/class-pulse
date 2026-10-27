"""Anonymous audience routes: join, live view, and response submission.

Everything here is reachable without authentication, so inputs are validated
strictly: session codes must match the 6-char format, choice answers must be
one of the question's options, free-text answers are length-capped, and the
respondent cookie must be a well-formed UUID.
"""

import json
import math
import uuid

from flask import (
    flash, jsonify, make_response, redirect, render_template, request, url_for
)

from sqlalchemy.exc import IntegrityError

from .extensions import limiter
from .extensions import db
from .models import Question, Response, Session
from .models import utcnow_iso
from .questions import SCATTER_COLORS, SCATTER_SIZES, parsed_options, response_display_label
from .sockets import broadcast_results
from .utils import normalize_session_code, session_code_match

RESPONDENT_COOKIE_NAME = "classpulse_respondent"

# Length caps for free-text answers from the anonymous audience.
MAX_SHORT_ANSWER_LEN = 2000
MAX_WORD_CLOUD_LEN = 200
MAX_OTHER_LEN = 500


def _valid_respondent_id(value):
    """The respondent cookie must be a UUID we issued, not an arbitrary string."""
    if not value:
        return None
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _question_options(question):
    try:
        parsed = json.loads(question.options) if question.options else []
    except (json.JSONDecodeError, TypeError):
        parsed = []
    return parsed


def _extract_response_value(question):
    """Validate the submitted form against the question definition.

    Returns (response_value, error_message). Exactly one is non-None.
    """
    q_type = question.type
    field = f'response-{question.id}'

    if q_type == 'multiple_choice':
        options = [str(o) for o in _question_options(question)]
        chosen = request.form.get(field)
        if chosen is None:
            return None, "No response value submitted."
        if chosen not in options:
            return None, "Please choose one of the listed options."
        return chosen, None

    if q_type == 'multi_select':
        options = [str(o) for o in _question_options(question)]
        chosen = [v for v in request.form.getlist(field) if v.strip()]
        if not chosen:
            return None, "Please select at least one option."
        if any(v not in options for v in chosen):
            return None, "Please choose from the listed options."
        # Dedupe while preserving order.
        return "\n".join(dict.fromkeys(chosen)), None

    if q_type == 'ranking':
        opts = [str(o) for o in _question_options(question)]
        assigned, ok = {}, True
        for idx, opt in enumerate(opts):
            raw_rank = request.form.get(f'rank-{question.id}-{idx}')
            try:
                assigned[opt] = int(raw_rank)
            except (TypeError, ValueError):
                ok = False
        if not ok or sorted(assigned.values()) != list(range(1, len(opts) + 1)):
            return None, "Assign a unique rank (1–N) to every option."
        ordered = [o for o, _ in sorted(assigned.items(),
                                        key=lambda kv: (kv[1], opts.index(kv[0])))]
        return "\n".join(ordered), None

    if q_type == 'multiple_choice_other':
        options = [str(o) for o in _question_options(question)]
        chosen = request.form.get(field)
        if chosen == '__other__':
            other = request.form.get(f'{field}-other', '').strip()
            if not other:
                return None, "Please enter your 'Other' answer."
            if len(other) > MAX_OTHER_LEN:
                return None, f"'Other' answers are limited to {MAX_OTHER_LEN} characters."
            return other, None
        if chosen is None:
            return None, "No response value submitted."
        if chosen not in options:
            return None, "Please choose one of the listed options."
        return chosen, None

    if q_type == 'rating':
        try:
            config = json.loads(question.options) if question.options else {}
            max_rating = int(config.get('max_rating', 5))
        except (json.JSONDecodeError, AttributeError, ValueError, TypeError):
            max_rating = 5
        raw = request.form.get(field)
        try:
            rating = int(raw)
        except (TypeError, ValueError):
            return None, "Please choose a rating."
        if not 1 <= rating <= max_rating:
            return None, f"Rating must be between 1 and {max_rating}."
        return str(rating), None

    if q_type == 'numeric':
        raw = request.form.get(field)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None, "Please enter a valid number."
        # float() also accepts "nan" and "inf". NaN slips past every min/max
        # comparison, and either one turns the stats average into a value
        # JSON can't carry, which breaks the presenter's live view.
        if not math.isfinite(value):
            return None, "Please enter a valid number."
        cfg = _question_options(question)
        if isinstance(cfg, dict):
            try:
                if 'min' in cfg and value < float(cfg['min']):
                    return None, f"Value must be at least {cfg['min']}."
                if 'max' in cfg and value > float(cfg['max']):
                    return None, f"Value must be at most {cfg['max']}."
            except (ValueError, TypeError):
                pass
        return raw.strip(), None

    if q_type == 'image_choice':
        items = _question_options(question)
        labels = [str(it.get('label', '')) for it in items] if isinstance(items, list) else []
        chosen = request.form.get(field)
        if chosen is None:
            return None, "No response value submitted."
        if chosen not in labels:
            return None, "Please choose one of the listed images."
        return chosen, None

    if q_type == 'emoji':
        emojis = _question_options(question)
        if not isinstance(emojis, list):
            emojis = []
        chosen = request.form.get(field)
        if chosen is None:
            return None, "No response value submitted."
        if chosen not in emojis:
            return None, "Please choose one of the listed emojis."
        return chosen, None

    if q_type == 'matrix':
        cfg = _question_options(question)
        if not isinstance(cfg, dict):
            cfg = {}
        try:
            cols = int(cfg.get('cols', 2))
            rows = int(cfg.get('rows', 2))
            col, row = (int(v) for v in str(request.form.get(field) or '').split(','))
        except (ValueError, TypeError):
            return None, "Please tap a cell in the grid."
        if not (1 <= col <= cols and 1 <= row <= rows):
            return None, "That cell is outside the grid."
        return f"{col},{row}", None

    if q_type == 'scatter':
        cfg = _question_options(question)
        if not isinstance(cfg, dict):
            cfg = {}
        try:
            x = float(request.form.get(f'{field}-x'))
            y = float(request.form.get(f'{field}-y'))
        except (TypeError, ValueError):
            return None, "Please tap the plot to place your point."
        if not (0 <= x <= 100 and 0 <= y <= 100):
            return None, "Your point is outside the plot."
        point = {"x": round(x, 1), "y": round(y, 1)}
        if cfg.get('allow_color'):
            c = str(request.form.get(f'{field}-color') or '')
            if c not in SCATTER_COLORS:
                return None, "Please pick a colour."
            point["c"] = c
        if cfg.get('allow_size'):
            s = str(request.form.get(f'{field}-size') or '')
            if s not in SCATTER_SIZES:
                return None, "Please pick a size."
            point["s"] = s
        return json.dumps(point, separators=(',', ':')), None

    # word_cloud, short_answer: free text with length caps.
    raw = request.form.get(field)
    if raw is None:
        return None, "No response value submitted."
    text = raw.strip()
    if not text:
        return None, "Please enter an answer."
    cap = MAX_WORD_CLOUD_LEN if q_type == 'word_cloud' else MAX_SHORT_ANSWER_LEN
    if len(text) > cap:
        return None, f"Answers are limited to {cap} characters."
    return text, None


def _save_response(question, respondent_id, value):
    """Insert or replace this respondent's answer to the question.

    A unique index on (question_id, respondent_id) backs this up: if a double
    tap races two inserts, the loser hits IntegrityError and updates the row
    the winner wrote, so the vote still counts once.
    """
    for _ in range(2):
        existing = Response.query.filter_by(question_id=question.id,
                                            respondent_id=respondent_id).first()
        if existing:
            existing.response_value = value
            existing.created_at = utcnow_iso()
        else:
            db.session.add(Response(question_id=question.id, session_id=question.session_id,
                                    response_value=value, respondent_id=respondent_id))
        try:
            db.session.commit()
            return
        except IntegrityError:
            db.session.rollback()
    raise RuntimeError("Could not save response after a concurrent insert")


def init_app(app):

    def _with_respondent_cookie(response, respondent_id):
        """Attach the anonymous respondent id. It identifies one browser to
        itself so answers can be de-duplicated and re-shown; it carries no
        personal data. Re-setting it on each view slides the 30-day expiry."""
        response.set_cookie(
            RESPONDENT_COOKIE_NAME,
            respondent_id,
            max_age=60 * 60 * 24 * 30,  # 30 days
            httponly=True,
            samesite='Lax',
            secure=app.config['SESSION_COOKIE_SECURE'],
        )
        return response

    @app.route('/join', methods=['GET', 'POST'])
    @limiter.limit("30 per minute", methods=["POST"])
    def join():
        if request.method == 'POST':
            code = normalize_session_code(request.form.get('code'))
            current_session = None
            if len(code) == 6 and code.isalnum():
                current_session = Session.query.filter(
                    session_code_match(code), Session.active.is_(True),
                    Session.archived.is_(False), Session.deleted.is_(False)).first()

            if current_session:
                respondent_id = _valid_respondent_id(
                    request.cookies.get(RESPONDENT_COOKIE_NAME)) or str(uuid.uuid4())
                # Redirect to the stored spelling, not what was typed, so the
                # URL and any later share of it are canonical.
                return _with_respondent_cookie(
                    make_response(
                        redirect(url_for('audience_view', code=current_session.code))),
                    respondent_id)
            flash("Invalid, inactive, archived, or deleted session code. Please try again.",
                  "danger")
            return render_template('join.html', code=code)

        # Prefill from ?code= so a /join?code=ABC123 link only needs one tap.
        return render_template('join.html',
                               code=normalize_session_code(request.args.get('code')))

    @app.route('/audience/<code>')
    def audience_view(code):
        current_session = Session.query.filter(
            session_code_match(code), Session.active.is_(True),
            Session.archived.is_(False), Session.deleted.is_(False)).first()
        if not current_session:
            flash("Session not found, is inactive, archived, or has been deleted.", "warning")
            return redirect(url_for('join'))

        # This route is where a QR scan or a shared join link lands, so most
        # first-time visitors arrive with no cookie. Mint one rather than
        # bouncing them to the join form to type a code they just scanned.
        respondent_id = (_valid_respondent_id(request.cookies.get(RESPONDENT_COOKIE_NAME))
                         or str(uuid.uuid4()))

        active_questions = [q for q in current_session.questions if q.active]

        # Get previous responses for this user in this session
        previous_responses_db = Response.query.filter_by(
            session_id=current_session.id, respondent_id=respondent_id).all()
        previous_responses = {r.question_id: r.response_value for r in previous_responses_db}
        # Raw stored values like "2,1" or scatter JSON mean nothing to a human;
        # precompute friendly labels for the "you chose …" status lines.
        previous_labels = {q.id: response_display_label(q.type, previous_responses.get(q.id),
                                                        parsed_options(q))
                           for q in active_questions if q.id in previous_responses}
        # Screen readers announce each matrix cell by its axis position
        # ("Impact: high, Likelihood: low") rather than a bare coordinate.
        cell_labels = {}
        for q in active_questions:
            if q.type != 'matrix':
                continue
            cfg = parsed_options(q)
            cfg = cfg if isinstance(cfg, dict) else {}
            try:
                cols, rows = int(cfg.get('cols', 2)), int(cfg.get('rows', 2))
            except (ValueError, TypeError):
                cols = rows = 2
            cell_labels[q.id] = {f'{c},{r}': response_display_label('matrix', f'{c},{r}', cfg)
                                 for c in range(1, cols + 1) for r in range(1, rows + 1)}

        return _with_respondent_cookie(
            make_response(render_template('audience_view.html',
                                          current_session=current_session,
                                          questions=active_questions,
                                          active_question_ids=[q.id for q in active_questions],
                                          previous_labels=previous_labels,
                                          cell_labels=cell_labels,
                                          scatter_colors=SCATTER_COLORS,
                                          scatter_sizes=SCATTER_SIZES,
                                          previous_responses=previous_responses)),
            respondent_id)

    @app.route('/audience/respond/<int:question_id>', methods=['POST'])
    @limiter.limit("60 per minute")
    def process_response(question_id):
        # Audience view submits via fetch() with this header; fall back to the
        # classic redirect/flash flow for non-JS clients.
        wants_json = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        question = Question.query.get_or_404(question_id)
        if (not question.active or not question.session.active
                or question.session.archived or question.session.deleted):
            msg = "Sorry, this question or session is no longer active."
            if wants_json:
                return jsonify({"success": False, "message": msg, "inactive": True}), 409
            flash(msg, "warning")
            return redirect(url_for('audience_view', code=question.session.code))

        respondent_id = _valid_respondent_id(request.cookies.get(RESPONDENT_COOKIE_NAME))
        if not respondent_id:
            msg = "Could not identify you. Please try rejoining the session."
            if wants_json:
                return jsonify({"success": False, "message": msg, "needs_rejoin": True}), 400
            flash(msg, "warning")
            return redirect(url_for('join'))

        response_value, err_msg = _extract_response_value(question)
        if err_msg:
            if wants_json:
                return jsonify({"success": False, "message": err_msg}), 400
            flash(err_msg, "warning")
            return redirect(url_for('audience_view', code=question.session.code))

        _save_response(question, respondent_id, response_value)

        # Notify presenters via WebSocket
        broadcast_results(question_id)

        if wants_json:
            return jsonify({
                "success": True,
                "message": "Your response was submitted!",
                "response_value": response_value,
                "response_label": response_display_label(question.type, response_value,
                                                         parsed_options(question)),
            })
        flash("Your response was submitted!", "success")
        return redirect(url_for('audience_view', code=question.session.code))

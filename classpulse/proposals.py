"""Cohort mode: anonymous audience members propose questions and upvote each
other's; the presenter approves (converting to a real Question), rejects, or
overrides moderation flags. See moderation.py for the filtering pipeline.
"""

import json

from flask import jsonify, request, session

from .audience import RESPONDENT_COOKIE_NAME, _valid_respondent_id
from .auth import login_required
from .extensions import db, limiter
from .models import Proposal, ProposalVote, Question, Session
from .moderation import moderate_proposal
from .questions import parse_question_payload, question_to_dict
from .sockets import broadcast_proposals_changed, broadcast_questions_changed

# Types the audience may propose. Deliberately narrower than
# VALID_QUESTION_TYPES: no image_choice (anonymous users supplying image URLs
# is an abuse vector) and none of the config-heavy types.
PROPOSAL_TYPES = ('multiple_choice', 'multi_select', 'short_answer', 'word_cloud', 'rating')

# Per-respondent cap per session; rejected ones don't count against it.
MAX_PROPOSALS_PER_RESPONDENT = 5

FLAGGED_MESSAGE = ("Based on this session's filters, your question needs presenter "
                   "approval before it appears in the public list.")


def _live_session_by_code(code):
    return Session.query.filter_by(code=(code or '').upper(), active=True,
                                   archived=False, deleted=False).first()


def proposal_to_dict(p, respondent_id=None):
    try:
        options = json.loads(p.options) if p.options else []
    except (json.JSONDecodeError, TypeError):
        options = []
    return {
        'id': p.id,
        'type': p.type,
        'title': p.title,
        'options': options,
        'status': p.status,
        'votes': len(p.votes),
        'my_vote': bool(respondent_id and any(v.respondent_id == respondent_id
                                              for v in p.votes)),
        'mine': bool(respondent_id and p.respondent_id == respondent_id),
        'flag_reason': p.flag_reason,
        'similar_to_id': p.similar_to_id,
        'created_at': p.created_at,
    }


def _public_sort_key(d):
    # Most-voted first, newest first among ties.
    return (-d['votes'], d['created_at'] or '')


def _proposals_used(session_id, respondent_id):
    """How many proposals count against the respondent's cap. Rejected and
    merged ones don't — a merge is the presenter's tidying, not the student's
    fault."""
    return Proposal.query.filter(
        Proposal.session_id == session_id,
        Proposal.respondent_id == respondent_id,
        Proposal.status.notin_(('rejected', 'merged'))).count()


def init_app(app):

    # ---------- Audience (anonymous) ----------

    @app.route('/audience/<code>/proposals', methods=['GET'])
    def audience_list_proposals(code):
        s = _live_session_by_code(code)
        if not s or not s.allow_proposals:
            return jsonify({"success": False, "enabled": False,
                            "message": "Proposals are not open for this session."}), 404
        respondent_id = _valid_respondent_id(request.cookies.get(RESPONDENT_COOKIE_NAME))
        proposals = Proposal.query.filter_by(session_id=s.id).all()
        public = [proposal_to_dict(p, respondent_id) for p in proposals
                  if p.status in ('visible', 'approved')]
        public.sort(key=_public_sort_key)
        # Submitters can also see their own hidden/rejected/merged ones, with status.
        mine_hidden = [proposal_to_dict(p, respondent_id) for p in proposals
                       if p.respondent_id == respondent_id
                       and p.status in ('flagged', 'rejected', 'merged')] if respondent_id else []
        remaining = MAX_PROPOSALS_PER_RESPONDENT
        if respondent_id:
            used = _proposals_used(s.id, respondent_id)
            remaining = max(0, MAX_PROPOSALS_PER_RESPONDENT - used)
        return jsonify({"success": True, "enabled": True, "proposals": public,
                        "mine_hidden": mine_hidden, "remaining": remaining})

    @app.route('/audience/<code>/proposals', methods=['POST'])
    @limiter.limit("5 per minute")
    def audience_create_proposal(code):
        s = _live_session_by_code(code)
        if not s or not s.allow_proposals:
            return jsonify({"success": False,
                            "message": "Proposals are not open for this session."}), 404
        respondent_id = _valid_respondent_id(request.cookies.get(RESPONDENT_COOKIE_NAME))
        if not respondent_id:
            return jsonify({"success": False, "needs_rejoin": True,
                            "message": "Could not identify you. Please rejoin the session."}), 400

        data = request.get_json(silent=True) or {}
        if data.get('type') not in PROPOSAL_TYPES:
            return jsonify({"success": False, "message": "Invalid question type."}), 400
        err, q_type, title, opts = parse_question_payload(data)
        if err:
            return jsonify({"success": False, "message": err}), 400

        if _proposals_used(s.id, respondent_id) >= MAX_PROPOSALS_PER_RESPONDENT:
            return jsonify({"success": False,
                            "message": f"You've reached the limit of "
                                       f"{MAX_PROPOSALS_PER_RESPONDENT} proposals for "
                                       "this session."}), 429

        options_text = "\n".join(str(o) for o in opts) if isinstance(opts, list) else ''
        verdict = moderate_proposal(s.id, title, options_text)

        p = Proposal(session_id=s.id, respondent_id=respondent_id, type=q_type,
                     title=title, options=json.dumps(opts), status=verdict['status'],
                     flag_reason=verdict['flag_reason'],
                     similar_to_id=verdict['similar_to_id'])
        db.session.add(p)
        db.session.commit()
        broadcast_proposals_changed(s.id)

        body = {"success": True, "proposal": proposal_to_dict(p, respondent_id)}
        if p.status == 'flagged':
            body["message"] = FLAGGED_MESSAGE
        elif p.similar_to_id:
            body["message"] = ("Submitted! Heads up — a similar question already exists; "
                               "consider upvoting it instead.")
        else:
            body["message"] = "Submitted! Your question is now in the list."
        return jsonify(body)

    @app.route('/audience/proposals/<int:proposal_id>/vote', methods=['POST'])
    @limiter.limit("30 per minute")
    def audience_vote_proposal(proposal_id):
        p = Proposal.query.get_or_404(proposal_id)
        s = p.session
        if not s.is_live or not s.allow_proposals:
            return jsonify({"success": False,
                            "message": "Voting is closed for this session."}), 409
        if p.status != 'visible':
            return jsonify({"success": False,
                            "message": "This question can't be voted on."}), 400
        respondent_id = _valid_respondent_id(request.cookies.get(RESPONDENT_COOKIE_NAME))
        if not respondent_id:
            return jsonify({"success": False, "needs_rejoin": True,
                            "message": "Could not identify you. Please rejoin the session."}), 400

        existing = ProposalVote.query.filter_by(proposal_id=p.id,
                                                respondent_id=respondent_id).first()
        if existing:
            db.session.delete(existing)
            voted = False
        else:
            db.session.add(ProposalVote(proposal_id=p.id, respondent_id=respondent_id))
            voted = True
        db.session.commit()
        broadcast_proposals_changed(s.id)
        return jsonify({"success": True, "voted": voted,
                        "votes": ProposalVote.query.filter_by(proposal_id=p.id).count()})

    # ---------- Presenter ----------

    def _owned_proposal_or_error(proposal_id):
        p = Proposal.query.get_or_404(proposal_id)
        if p.session.user_id != session['user_id']:
            return None, (jsonify({"success": False, "message": "Permission denied."}), 403)
        return p, None

    @app.route('/api/sessions/<int:session_id>/proposals/toggle', methods=['POST'])
    @login_required
    def api_toggle_proposals(session_id):
        s = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
        if s.archived or s.deleted:
            return jsonify({"success": False, "message": "Cannot modify this session."}), 400
        s.allow_proposals = not s.allow_proposals
        db.session.commit()
        broadcast_proposals_changed(s.id)
        return jsonify({"success": True, "enabled": s.allow_proposals})

    @app.route('/api/sessions/<int:session_id>/proposals', methods=['GET'])
    @login_required
    def api_list_proposals(session_id):
        s = Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()
        proposals = [proposal_to_dict(p) for p in Proposal.query.filter_by(session_id=s.id)]
        flagged = [p for p in proposals if p['status'] == 'flagged']
        visible = sorted([p for p in proposals if p['status'] == 'visible'],
                         key=_public_sort_key)
        done = [p for p in proposals if p['status'] in ('approved', 'rejected', 'merged')]
        return jsonify({"success": True, "enabled": s.allow_proposals,
                        "flagged": flagged, "visible": visible, "done": done})

    @app.route('/api/proposals/<int:proposal_id>/approve', methods=['POST'])
    @login_required
    def api_approve_proposal(proposal_id):
        """Convert a proposal into a real (live) Question.

        The body may carry edited {type,title,options,max_rating} — otherwise
        the proposal's own content is used. Either way it goes through the
        same validation as presenter-authored questions.
        """
        p, err = _owned_proposal_or_error(proposal_id)
        if err:
            return err
        s = p.session
        if s.archived or s.deleted:
            return jsonify({"success": False, "message": "Cannot modify this session."}), 400
        if p.status == 'approved':
            return jsonify({"success": False, "message": "Already approved."}), 400

        data = request.get_json(silent=True) or {}
        if not data.get('title'):
            try:
                opts = json.loads(p.options) if p.options else []
            except (json.JSONDecodeError, TypeError):
                opts = []
            data = {'type': p.type, 'title': p.title, 'options': opts}
            if p.type == 'rating' and isinstance(opts, dict):
                data['max_rating'] = opts.get('max_rating', 5)
        parse_err, q_type, title, options_value = parse_question_payload(data)
        if parse_err:
            return jsonify({"success": False, "message": parse_err}), 400

        next_order = max([q.order for q in s.questions], default=0) + 1
        q = Question(session_id=s.id, type=q_type, title=title,
                     options=json.dumps(options_value), active=True, order=next_order)
        db.session.add(q)
        db.session.flush()
        p.status = 'approved'
        p.flag_reason = None
        p.question_id = q.id
        db.session.commit()
        broadcast_questions_changed(s.id)
        broadcast_proposals_changed(s.id)
        return jsonify({"success": True, "question": question_to_dict(q),
                        "proposal": proposal_to_dict(p)})

    @app.route('/api/proposals/<int:proposal_id>/reject', methods=['POST'])
    @login_required
    def api_reject_proposal(proposal_id):
        p, err = _owned_proposal_or_error(proposal_id)
        if err:
            return err
        p.status = 'rejected'
        db.session.commit()
        broadcast_proposals_changed(p.session_id)
        return jsonify({"success": True, "proposal": proposal_to_dict(p)})

    @app.route('/api/proposals/<int:proposal_id>/merge', methods=['POST'])
    @login_required
    def api_merge_proposal(proposal_id):
        """Fold a duplicate proposal into another, transferring its votes.

        Body: {"into": <proposal_id>} — defaults to the similarity hint
        (similar_to_id) when omitted. Each respondent still counts at most
        once on the target; the source is marked 'merged' and hidden from
        the public list, with similar_to_id pointing at the target.
        """
        p, err = _owned_proposal_or_error(proposal_id)
        if err:
            return err
        data = request.get_json(silent=True) or {}
        target_id = data.get('into') or p.similar_to_id
        try:
            target_id = int(target_id)
        except (TypeError, ValueError):
            return jsonify({"success": False,
                            "message": "No merge target — pass {\"into\": id}."}), 400
        if target_id == p.id:
            return jsonify({"success": False,
                            "message": "Cannot merge a proposal into itself."}), 400
        target = db.session.get(Proposal, target_id)
        if not target or target.session_id != p.session_id:
            return jsonify({"success": False,
                            "message": "Merge target must be a proposal in the "
                                       "same session."}), 400
        if p.status not in ('visible', 'flagged'):
            return jsonify({"success": False,
                            "message": "Only open proposals can be merged."}), 400
        if target.status not in ('visible', 'approved'):
            return jsonify({"success": False,
                            "message": "Merge target must be visible or approved."}), 400

        already_voted = {v.respondent_id for v in target.votes}
        for vote in list(p.votes):
            if vote.respondent_id in already_voted:
                db.session.delete(vote)  # would double-count — drop it
            else:
                vote.proposal = target  # reparent via the relationship
                already_voted.add(vote.respondent_id)
        p.status = 'merged'
        p.similar_to_id = target.id
        p.flag_reason = None
        db.session.commit()
        broadcast_proposals_changed(p.session_id)
        return jsonify({"success": True, "proposal": proposal_to_dict(p),
                        "target": proposal_to_dict(target)})

    @app.route('/api/proposals/<int:proposal_id>/unflag', methods=['POST'])
    @login_required
    def api_unflag_proposal(proposal_id):
        """Presenter override: publish a flagged proposal to the audience list."""
        p, err = _owned_proposal_or_error(proposal_id)
        if err:
            return err
        if p.status != 'flagged':
            return jsonify({"success": False, "message": "Only flagged proposals "
                                                         "can be unflagged."}), 400
        p.status = 'visible'
        p.flag_reason = None
        db.session.commit()
        broadcast_proposals_changed(p.session_id)
        return jsonify({"success": True, "proposal": proposal_to_dict(p)})

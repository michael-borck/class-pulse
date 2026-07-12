"""Presenter-facing pages and the session/question authoring API."""

import csv
import io
import json

from flask import (
    abort, flash, jsonify, redirect, render_template, request, send_file,
    session, url_for
)

from .ai import generate_question_with_ai
from .auth import login_required
from .extensions import db, limiter
from .models import Question, Response, Session
from .questions import (
    parse_question_payload, question_to_dict, session_to_dict
)
from .sockets import broadcast_questions_changed
from .utils import create_qr_code_data, csv_safe, generate_session_code


def _owned_session_or_404(session_id):
    return Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()


def _render_dashboard(selected_id=None):
    """Render the unified master-detail dashboard. Used at /dashboard (no
    selection) and /sessions/<id> (a session selected, which doubles as the
    deep link)."""
    user_id = session['user_id']
    # Include archived (client filters via the Active/Archived tabs); exclude deleted.
    user_sessions = Session.query.filter_by(user_id=user_id, deleted=False) \
        .order_by(Session.created_at.desc()).all()
    sessions_data = [session_to_dict(s) for s in user_sessions]
    selected = None
    if selected_id is not None:
        sel = next((s for s in user_sessions if s.id == selected_id), None)
        if sel:
            selected = session_to_dict(sel, include_questions=True)
            selected['join_url'] = url_for('audience_view', code=sel.code, _external=True)
            selected['qr'] = create_qr_code_data(selected['join_url'])
    return render_template('dashboard.html', sessions=sessions_data, selected=selected)


def _send_responses_csv(responses, filename):
    """Stream a list of Response rows as a CSV download.

    response_value is audience-controlled, so it goes through csv_safe() to
    neutralise spreadsheet formula injection.
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "response_id", "question_id", "session_id",
        "response_value", "respondent_id", "timestamp",
    ])
    writer.writeheader()
    for r in responses:
        writer.writerow({
            "response_id": r.id, "question_id": r.question_id, "session_id": r.session_id,
            "response_value": csv_safe(r.response_value), "respondent_id": r.respondent_id,
            "timestamp": r.created_at,
        })
    mem_output = io.BytesIO(output.getvalue().encode('utf-8'))
    output.close()
    return send_file(mem_output, as_attachment=True, download_name=filename, mimetype='text/csv')


def init_app(app):

    # --- Pages ---

    @app.route('/')
    def index():
        """Public landing page. Authenticated visitors skip straight to the app."""
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        return render_template('landing.html')

    @app.route('/dashboard')
    @login_required
    def dashboard():
        return _render_dashboard()

    @app.route('/sessions')
    @login_required
    def list_sessions():
        # Legacy URL from the pre-dashboard UI; keep old bookmarks working.
        return redirect(url_for('dashboard'))

    @app.route('/sessions/<int:session_id>')
    @login_required
    def manage_session(session_id):
        # The session builder is the unified dashboard with this session selected;
        # this URL is also the shareable deep link.
        current_session = _owned_session_or_404(session_id)
        if current_session.deleted:
            flash("This session has been deleted.", "warning")
            return redirect(url_for('dashboard'))
        return _render_dashboard(selected_id=session_id)

    @app.route('/present/<int:session_id>')
    @login_required
    def present_mode(session_id):
        current_session = _owned_session_or_404(session_id)
        if current_session.archived:
            flash("Cannot present an archived session.", "warning")
            return redirect(url_for('manage_session', session_id=session_id))
        if current_session.deleted:
            flash("Cannot present a deleted session.", "warning")
            return redirect(url_for('dashboard'))

        active_questions = [q for q in current_session.questions if q.active]
        join_url = url_for('audience_view', code=current_session.code, _external=True)
        qr_code_data_url = create_qr_code_data(join_url, size=150)
        return render_template('present_mode.html',
                               current_session=current_session,
                               active_questions=active_questions,
                               join_url=join_url,
                               qr_code_data_url=qr_code_data_url,
                               mode='present')

    @app.route('/sessions/<int:session_id>/results')
    @login_required
    def session_results(session_id):
        """Post-hoc results view — same Focus/Grid/Stack layouts as Present, over
        all questions, available even when the session is no longer active."""
        current_session = _owned_session_or_404(session_id)
        if current_session.deleted:
            flash("This session has been deleted.", "warning")
            return redirect(url_for('dashboard'))
        return render_template('present_mode.html',
                               current_session=current_session,
                               active_questions=list(current_session.questions),
                               join_url=None,
                               qr_code_data_url=None,
                               mode='results')

    @app.route('/questions/<int:question_id>/results')
    @login_required
    def view_question_results(question_id):
        from .stats import get_question_stats
        question = Question.query.get_or_404(question_id)
        if question.session.user_id != session['user_id']:
            abort(403)
        stats = get_question_stats(question_id)
        return render_template('question_results.html', question=question, stats=stats)

    # --- Exports ---

    @app.route('/questions/<int:question_id>/export')
    @login_required
    def export_question_results(question_id):
        question = Question.query.get_or_404(question_id)
        if question.session.user_id != session['user_id']:
            abort(403)
        all_responses = Response.query.filter_by(question_id=question_id) \
            .order_by(Response.created_at).all()
        if not all_responses:
            flash("No responses to export for this question.", "info")
            return redirect(url_for('view_question_results', question_id=question_id))
        return _send_responses_csv(all_responses, f"classpulse_q_{question_id}_results.csv")

    @app.route('/sessions/<int:session_id>/export')
    @login_required
    def export_session_results(session_id):
        _owned_session_or_404(session_id)  # ownership check
        all_responses = Response.query.filter_by(session_id=session_id) \
            .order_by(Response.question_id, Response.created_at).all()
        if not all_responses:
            flash("No responses to export for this session.", "info")
            return redirect(url_for('manage_session', session_id=session_id))
        return _send_responses_csv(all_responses,
                                   f"classpulse_session_{session_id}_all_results.csv")

    # --- AI generation API ---

    @app.route('/api/test-ai-generation', methods=['POST'])
    @login_required
    @limiter.limit("10 per minute")
    def api_test_ai_generation():
        """Generate or refine a question with AI.

        JSON payload: {"mode": "generate"|"refine", ...}. Defaults to "generate".
        Backward compatible with the legacy {"prompt": "..."} (treated as generate).
          - generate: {"mode":"generate","instruction":"..."}  (or {"prompt":"..."})
          - refine:   {"mode":"refine","type":"...","title":"...","options":[...],"hint":"..."}
        """
        try:
            data = request.get_json() or {}
            mode = (data.get("mode") or "generate").strip().lower()
            if mode == "refine":
                result = generate_question_with_ai(
                    mode="refine",
                    title=data.get("title"),
                    options=data.get("options"),
                    hint=data.get("hint"),
                    qtype=data.get("type"),
                )
            else:
                instruction = data.get("instruction") or data.get("prompt")
                if not instruction:
                    return jsonify({"success": False, "error": "No instruction provided"}), 400
                result = generate_question_with_ai(mode="generate", instruction=instruction)
            return jsonify(result)
        except Exception:
            app.logger.exception("AI generation failed")
            return jsonify({"success": False, "error": "Question generation failed."}), 500

    # --- Session API ---

    @app.route('/api/sessions', methods=['POST'])
    @login_required
    def api_create_session():
        """Create a new (inactive) session and return it for the builder."""
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or 'Untitled session').strip()[:100] or 'Untitled session'
        s = Session(name=name, code=generate_session_code(), user_id=session['user_id'],
                    active=False, archived=False, deleted=False)
        db.session.add(s)
        db.session.commit()
        return jsonify({"success": True, "session": session_to_dict(s, include_questions=True)})

    @app.route('/api/sessions/<int:session_id>/rename', methods=['POST'])
    @login_required
    def api_rename_session(session_id):
        s = _owned_session_or_404(session_id)
        name = ((request.get_json(silent=True) or {}).get('name') or '').strip()[:100]
        if not name:
            return jsonify({"success": False, "message": "Name is required."}), 400
        s.name = name
        db.session.commit()
        return jsonify({"success": True, "name": s.name})

    @app.route('/api/sessions/<int:session_id>/toggle', methods=['POST'])
    @login_required
    def api_toggle_session(session_id):
        current_session = _owned_session_or_404(session_id)
        if current_session.archived:
            return jsonify({"success": False, "message": "Cannot toggle archived session."}), 400
        if current_session.deleted:
            return jsonify({"success": False, "message": "Cannot toggle deleted session."}), 400
        current_session.active = not current_session.active
        db.session.commit()
        # Notify audience members so an inactive session boots them out live
        broadcast_questions_changed(current_session.id)
        return jsonify({"success": True, "active": current_session.active,
                        "new_text": "Deactivate" if current_session.active else "Activate"})

    @app.route('/api/sessions/<int:session_id>/archive', methods=['POST'])
    @login_required
    def api_archive_session(session_id):
        """Toggle session archive status."""
        current_session = _owned_session_or_404(session_id)
        if current_session.deleted:
            return jsonify({"success": False, "message": "Cannot archive a deleted session."}), 400
        current_session.archived = not current_session.archived
        if current_session.archived:
            current_session.active = False
        db.session.commit()
        if current_session.archived:
            broadcast_questions_changed(current_session.id)
        return jsonify({"success": True, "archived": current_session.archived,
                        "new_text": "Unarchive" if current_session.archived else "Archive"})

    @app.route('/api/sessions/<int:session_id>/delete', methods=['POST'])
    @login_required
    def api_delete_session(session_id):
        """Delete a session (soft delete with data, hard delete if empty)."""
        current_session = _owned_session_or_404(session_id)
        if current_session.deleted:
            return jsonify({"success": False, "message": "Session is already deleted."}), 400

        response_count = Response.query.filter_by(session_id=session_id).count()
        if response_count > 0:
            # Soft delete — has responses, so preserve data.
            current_session.deleted = True
            current_session.active = False
            db.session.commit()
            broadcast_questions_changed(current_session.id)
            return jsonify({"success": True, "deleted": "soft",
                            "message": f"Session moved to trash ({response_count} responses kept)."})
        # Hard delete — no responses, safe to permanently delete.
        Question.query.filter_by(session_id=session_id).delete()
        db.session.delete(current_session)
        db.session.commit()
        return jsonify({"success": True, "deleted": "hard",
                        "message": "Session permanently deleted (no responses)."})

    # --- Question API ---

    @app.route('/api/sessions/<int:session_id>/questions', methods=['GET', 'POST'])
    @login_required
    def api_session_questions(session_id):
        s = _owned_session_or_404(session_id)
        if request.method == 'GET':
            return jsonify({"success": True,
                            "questions": [question_to_dict(q) for q in s.questions]})
        # POST: create
        if s.archived or s.deleted:
            return jsonify({"success": False,
                            "message": "Cannot add questions to this session."}), 400
        err, q_type, title, opts = parse_question_payload(request.get_json(silent=True) or {})
        if err:
            return jsonify({"success": False, "message": err}), 400
        next_order = max([q.order for q in s.questions], default=0) + 1
        q = Question(session_id=s.id, type=q_type, title=title, options=json.dumps(opts),
                     active=True, order=next_order)
        db.session.add(q)
        db.session.commit()
        broadcast_questions_changed(s.id)
        return jsonify({"success": True, "question": question_to_dict(q)})

    @app.route('/api/questions/<int:question_id>/toggle', methods=['POST'])
    @login_required
    def api_toggle_question(question_id):
        question = Question.query.get_or_404(question_id)
        if question.session.user_id != session['user_id']:
            return jsonify({"success": False, "message": "Permission denied."}), 403
        if question.session.archived:
            return jsonify({"success": False,
                            "message": "Cannot toggle question in archived session."}), 400
        if question.session.deleted:
            return jsonify({"success": False,
                            "message": "Cannot toggle question in deleted session."}), 400
        question.active = not question.active
        db.session.commit()
        # Push the new active-question set to any audience members watching live
        broadcast_questions_changed(question.session_id)
        return jsonify({"success": True, "active": question.active,
                        "new_text": "Deactivate" if question.active else "Activate"})

    @app.route('/api/questions/<int:question_id>/edit', methods=['POST'])
    @login_required
    def api_edit_question(question_id):
        q = Question.query.get_or_404(question_id)
        if q.session.user_id != session['user_id']:
            return jsonify({"success": False, "message": "Permission denied."}), 403
        if q.session.archived or q.session.deleted:
            return jsonify({"success": False, "message": "Cannot edit this question."}), 400
        err, q_type, title, opts = parse_question_payload(request.get_json(silent=True) or {})
        if err:
            return jsonify({"success": False, "message": err}), 400
        # Title can always change; structural edits are blocked once responses exist
        # (they would orphan the recorded answers) — duplicate instead.
        structural = (q_type != q.type) or (json.dumps(opts) != (q.options or ''))
        if structural and Response.query.filter_by(question_id=q.id).count() > 0:
            q.title = title
            db.session.commit()
            return jsonify({"success": False, "partial": True,
                            "message": "Saved the title. Options/type can't change once "
                                       "responses exist — duplicate the question instead.",
                            "question": question_to_dict(q)})
        q.type, q.title, q.options = q_type, title, json.dumps(opts)
        db.session.commit()
        return jsonify({"success": True, "question": question_to_dict(q)})

    @app.route('/api/questions/<int:question_id>/duplicate', methods=['POST'])
    @login_required
    def api_duplicate_question(question_id):
        q = Question.query.get_or_404(question_id)
        if q.session.user_id != session['user_id']:
            return jsonify({"success": False, "message": "Permission denied."}), 403
        if q.session.archived or q.session.deleted:
            return jsonify({"success": False, "message": "Cannot modify this session."}), 400
        next_order = max([x.order for x in q.session.questions], default=0) + 1
        c = Question(session_id=q.session_id, type=q.type, title=f"{q.title} (copy)"[:255],
                     options=q.options, active=True, order=next_order)
        db.session.add(c)
        db.session.commit()
        return jsonify({"success": True, "question": question_to_dict(c)})

    @app.route('/api/questions/<int:question_id>/delete', methods=['POST'])
    @login_required
    def api_delete_question(question_id):
        """Delete a question (only if no responses exist)."""
        question = Question.query.get_or_404(question_id)
        if question.session.user_id != session['user_id']:
            return jsonify({"success": False, "message": "Permission denied."}), 403
        if question.session.archived or question.session.deleted:
            return jsonify({"success": False,
                            "message": "Cannot delete question in archived or deleted session."}), 400
        response_count = Response.query.filter_by(question_id=question_id).count()
        if response_count > 0:
            return jsonify({
                "success": False,
                "message": f"Cannot delete question with {response_count} response(s). "
                           "Deactivate instead."
            }), 400
        session_id = question.session_id
        db.session.delete(question)
        db.session.commit()
        # A deleted question may have been active; refresh audience views
        broadcast_questions_changed(session_id)
        return jsonify({"success": True, "message": "Question deleted successfully."})

    @app.route('/api/sessions/<int:session_id>/questions/reorder', methods=['POST'])
    @login_required
    def api_reorder_questions(session_id):
        s = _owned_session_or_404(session_id)
        order = (request.get_json(silent=True) or {}).get('order') or []
        pos = {qid: i for i, qid in enumerate(order)}
        for q in s.questions:
            if q.id in pos:
                q.order = pos[q.id]
        db.session.commit()
        return jsonify({"success": True})

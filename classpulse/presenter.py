"""Presenter-facing pages and the session/question authoring API."""

import csv
import io
import json

from flask import (
    abort, flash, jsonify, redirect, render_template, request, send_file,
    session, url_for
)

from .accounts import purge_session
from .ai import generate_question_with_ai
from .auth import login_required
from .extensions import db, limiter
from .models import Question, Response, Session
from .questions import (
    SCATTER_COLORS, build_answer, parse_question_payload, parsed_options, question_to_dict,
    session_to_dict,
)
from .sockets import broadcast_questions_changed, broadcast_results
from .utils import create_qr_code_data, csv_safe, generate_session_code, request_json_object


def _owned_session_or_404(session_id):
    return Session.query.filter_by(id=session_id, user_id=session['user_id']).first_or_404()


def _render_dashboard(selected_id=None):
    """Render the unified master-detail dashboard. Used at /dashboard (no
    selection) and /sessions/<id> (a session selected, which doubles as the
    deep link)."""
    user_id = session['user_id']
    # Include archived (client filters via the Active/Archived tabs).
    user_sessions = Session.query.filter_by(user_id=user_id) \
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
        _owned_session_or_404(session_id)
        return _render_dashboard(selected_id=session_id)

    @app.route('/present/<int:session_id>')
    @login_required
    def present_mode(session_id):
        current_session = _owned_session_or_404(session_id)
        if current_session.archived:
            flash("Cannot present an archived session.", "warning")
            return redirect(url_for('manage_session', session_id=session_id))

        active_questions = [q for q in current_session.questions if q.active]
        join_url = url_for('audience_view', code=current_session.code, _external=True)
        # Big enough to stay sharp when the join screen blows it up on a projector.
        qr_code_data_url = create_qr_code_data(join_url, size=720)
        # Shown as text next to the code, for anyone typing it in rather than scanning.
        manual_join_url = url_for('join', _external=True)
        return render_template('present_mode.html',
                               current_session=current_session,
                               active_questions=active_questions,
                               join_url=join_url,
                               manual_join_url=manual_join_url,
                               qr_code_data_url=qr_code_data_url,
                               scatter_colors=SCATTER_COLORS,
                               mode='present')

    @app.route('/sessions/<int:session_id>/results')
    @login_required
    def session_results(session_id):
        """Post-hoc results view — same Focus/Grid/Stack layouts as Present, over
        all questions, available even when the session is no longer active."""
        current_session = _owned_session_or_404(session_id)
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
        return render_template('question_results.html', question=question, stats=stats,
                               scatter_colors=SCATTER_COLORS)

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
            data = request_json_object()
            mode = str(data.get("mode") or "generate").strip().lower()
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
        name = str(request_json_object().get('name') or 'Untitled session').strip()[:100] \
            or 'Untitled session'
        s = Session(name=name, code=generate_session_code(), user_id=session['user_id'],
                    active=False, archived=False)
        db.session.add(s)
        db.session.commit()
        return jsonify({"success": True, "session": session_to_dict(s, include_questions=True)})

    @app.route('/api/sessions/<int:session_id>/rename', methods=['POST'])
    @login_required
    def api_rename_session(session_id):
        s = _owned_session_or_404(session_id)
        name = str(request_json_object().get('name') or '').strip()[:100]
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
        """Permanently delete a session and everything it holds. Irreversible.

        Results are disposable (no recovery use-case), so there is no trash to
        move to — responses, questions, proposals, and uploads all go.
        """
        _owned_session_or_404(session_id)
        purge_session(session_id)
        return jsonify({"success": True, "message": "Session permanently deleted."})

    # --- Question API ---

    @app.route('/api/sessions/<int:session_id>/questions', methods=['GET', 'POST'])
    @login_required
    def api_session_questions(session_id):
        s = _owned_session_or_404(session_id)
        if request.method == 'GET':
            return jsonify({"success": True,
                            "questions": [question_to_dict(q) for q in s.questions]})
        # POST: create
        if s.archived:
            return jsonify({"success": False,
                            "message": "Cannot add questions to this session."}), 400
        data = request_json_object()
        err, q_type, title, opts = parse_question_payload(data)
        answer, answer_err = build_answer(q_type, data, opts) if not err else (None, None)
        if err or answer_err:
            return jsonify({"success": False, "message": err or answer_err}), 400
        next_order = max([q.order for q in s.questions], default=0) + 1
        q = Question(session_id=s.id, type=q_type, title=title, options=json.dumps(opts),
                     answer=answer, active=True, order=next_order)
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
        if q.session.archived:
            return jsonify({"success": False, "message": "Cannot edit this question."}), 400
        data = request_json_object()
        err, q_type, title, opts = parse_question_payload(data)
        if err:
            return jsonify({"success": False, "message": err}), 400
        # Title can always change; structural edits are blocked once responses exist
        # (they would orphan the recorded answers) — duplicate instead.
        structural = (q_type != q.type) or (json.dumps(opts) != (q.options or ''))
        if structural and Response.query.filter_by(question_id=q.id).count() > 0:
            q.title = title
            # The quiz answer can still change (fixing a wrong key re-scores
            # the existing responses), as long as it fits the unchanged options.
            answer, answer_err = build_answer(q.type, data, parsed_options(q))
            if not answer_err:
                q.answer = answer
            db.session.commit()
            broadcast_questions_changed(q.session_id, edited_question_id=q.id)
            return jsonify({"success": False, "partial": True,
                            "message": "Saved the title. Options/type can't change once "
                                       "responses exist — duplicate the question instead.",
                            "question": question_to_dict(q)})
        answer, answer_err = build_answer(q_type, data, opts)
        if answer_err:
            return jsonify({"success": False, "message": answer_err}), 400
        q.type, q.title, q.options, q.answer = q_type, title, json.dumps(opts), answer
        if not answer:
            q.revealed = False
        db.session.commit()
        # The active-id set is unchanged, so name the edited question; open
        # audience pages and Present reload it rather than keep stale options.
        broadcast_questions_changed(q.session_id, edited_question_id=q.id)
        return jsonify({"success": True, "question": question_to_dict(q)})

    @app.route('/api/questions/<int:question_id>/duplicate', methods=['POST'])
    @login_required
    def api_duplicate_question(question_id):
        q = Question.query.get_or_404(question_id)
        if q.session.user_id != session['user_id']:
            return jsonify({"success": False, "message": "Permission denied."}), 403
        if q.session.archived:
            return jsonify({"success": False, "message": "Cannot modify this session."}), 400
        next_order = max([x.order for x in q.session.questions], default=0) + 1
        c = Question(session_id=q.session_id, type=q.type, title=f"{q.title} (copy)"[:255],
                     options=q.options, answer=q.answer, active=True, order=next_order)
        db.session.add(c)
        db.session.commit()
        broadcast_questions_changed(q.session_id)  # the copy starts active
        return jsonify({"success": True, "question": question_to_dict(c)})

    @app.route('/api/questions/<int:question_id>/reveal', methods=['POST'])
    @login_required
    def api_reveal_question(question_id):
        """Quiz mode: show (or hide again) the answer and results.

        Revealing also closes answering, and nudges open audience pages so each
        student sees whether they were right.
        """
        q = Question.query.get_or_404(question_id)
        if q.session.user_id != session['user_id']:
            return jsonify({"success": False, "message": "Permission denied."}), 403
        if not q.answer:
            return jsonify({"success": False, "message": "This question has no correct answer set."}), 400
        q.revealed = not q.revealed
        db.session.commit()
        broadcast_questions_changed(q.session_id, edited_question_id=q.id)
        broadcast_results(q.id)
        return jsonify({"success": True, "revealed": q.revealed})

    @app.route('/api/questions/<int:question_id>/delete', methods=['POST'])
    @login_required
    def api_delete_question(question_id):
        """Delete a question (only if no responses exist)."""
        question = Question.query.get_or_404(question_id)
        if question.session.user_id != session['user_id']:
            return jsonify({"success": False, "message": "Permission denied."}), 403
        if question.session.archived:
            return jsonify({"success": False,
                            "message": "Cannot delete question in an archived session."}), 400
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
        order = request_json_object().get('order')
        if not isinstance(order, list):
            order = []
        pos = {qid: i for i, qid in enumerate(order) if isinstance(qid, int)}
        for q in s.questions:
            if q.id in pos:
                q.order = pos[q.id]
        db.session.commit()
        return jsonify({"success": True})

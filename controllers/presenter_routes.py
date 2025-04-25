from fasthtml.common import *
import json
from datetime import datetime
from models.schema import users, User, sessions, Session, questions, Question, responses, Response
from utils.session_manager import (
    create_session, get_session_by_code, get_user_sessions,
    create_multiple_choice_question, create_word_cloud_question, create_rating_question,
    get_session_questions, toggle_question_status, toggle_session_status,
    get_question_stats
)
from utils.qrcode import create_qr_code_data
from utils.components import layout

def setup_presenter_routes(rt, app):
    """
    Set up presenter-related routes
    """
    
    @rt("/")
    def get(session):
        """Home/Dashboard page"""
        user_id = session.get('user_id')
        user = users[user_id] if user_id else None
        
        if not user:
            return RedirectResponse('/login')
        
        # Get active sessions
        user_sessions = get_user_sessions(user_id)
        active_sessions = [s for s in user_sessions if s.active]
        
        return layout(
            H2(f"Welcome, {user.display_name}!"),
            
            Div(
                H3("Active Sessions"),
                Div(
                    *[Div(
                        H4(s.name),
                        P(f"Code: {s.code}"),
                        Div(
                            A("Manage", href=f"/sessions/{s.id}", cls="button"),
                            A("Present", href=f"/present/{s.id}", cls="button primary"),
                            cls="actions"
                        ),
                        cls="session-card"
                    ) for s in active_sessions] if active_sessions else [P("No active sessions")],
                    cls="session-grid"
                ),
                cls="dashboard-section"
            ),
            
            Div(
                H3("Quick Actions"),
                Div(
                    A("Create New Session", href="/sessions/new", cls="button primary"),
                    A("View All Sessions", href="/sessions", cls="button"),
                    cls="button-group"
                ),
                cls="dashboard-section"
            )
        )

    @rt("/sessions")
    def get(session):
        """List all sessions for the current user"""
        user_id = session.get('user_id')
        
        # Get all sessions for the user
        user_sessions = get_user_sessions(user_id)
        
        return layout(
            H2("Your Sessions"),
            
            Div(
                A("Create New Session", href="/sessions/new", cls="button primary"),
                cls="actions-bar"
            ),
            
            Div(
                *[Div(
                    H3(s.name),
                    P(f"Code: {s.code}"),
                    P(f"Created: {datetime.fromisoformat(s.created_at).strftime('%Y-%m-%d %H:%M')}"),
                    P(Span("Active", cls="badge success") if s.active else Span("Inactive", cls="badge"), cls="status"),
                    Div(
                        A("Manage", href=f"/sessions/{s.id}", cls="button"),
                        A("Present", href=f"/present/{s.id}", cls="button primary"),
                        cls="actions"
                    ),
                    cls="session-card"
                ) for s in user_sessions] if user_sessions else [P("No sessions found. Create your first session!")],
                cls="session-grid"
            ),
            
            title="Sessions - ClassPulse"
        )

    @rt("/sessions/new")
    def get():
        """Create new session form"""
        return layout(
            H2("Create New Session"),
            
            Form(
                Div(
                    Label("Session Name", For="name"),
                    Input(id="name", name="name", required=True),
                    cls="form-group"
                ),
                Button("Create Session", type="submit", cls="button primary"),
                method="post",
                action="/sessions/new"
            ),
            
            title="New Session - ClassPulse"
        )

    @rt("/sessions/new")
    def post(name: str, session):
        """Handle new session creation"""
        user_id = session.get('user_id')
        
        # Create the session
        new_session = create_session(user_id, name)
        
        return RedirectResponse(f'/sessions/{new_session.id}', status_code=303)

    @rt("/sessions/{id}")
    def get(id: int, session):
        """Session management page"""
        user_id = session.get('user_id')
        
        # Get session and verify ownership
        session_obj = sessions[id]
        if not session_obj or session_obj.user_id != user_id:
            return RedirectResponse('/sessions', status_code=303)
        
        # Get questions for this session
        session_questions = get_session_questions(id)
        
        # Create join URL and QR code
        join_url = f"{app.host_url}/audience/{session_obj.code}"
        qr_code = create_qr_code_data(join_url)
        
        return layout(
            H2(f"Manage Session: {session_obj.name}"),
            
            Div(
                H3("Session Information"),
                Div(
                    Div(
                        P(f"Code: ", Strong(session_obj.code)),
                        P(f"Status: ", 
                          Span("Active", cls="badge success") if session_obj.active else Span("Inactive", cls="badge")),
                        P(f"Created: {datetime.fromisoformat(session_obj.created_at).strftime('%Y-%m-%d %H:%M')}"),
                        P(A("Join URL: ", Strong(join_url), href=join_url, target="_blank")),
                        Div(
                            Button(
                                "Toggle Status", 
                                hx_post=f"/api/sessions/{id}/toggle",
                                hx_swap="outerHTML",
                                hx_target="#session-actions"
                            ),
                            A("Present Mode", href=f"/present/{id}", cls="button primary"),
                            id="session-actions",
                            cls="actions"
                        ),
                        cls="session-info"
                    ),
                    Div(
                        Img(src=qr_code, alt=f"QR Code for session {session_obj.code}"),
                        cls="qr-code"
                    ) if qr_code else None,
                    cls="session-header"
                ),
                cls="section"
            ),
            
            Div(
                H3("Questions"),
                Div(
                    A("New Multiple Choice", href=f"/sessions/{id}/questions/new/multiple_choice", cls="button"),
                    A("New Word Cloud", href=f"/sessions/{id}/questions/new/word_cloud", cls="button"),
                    A("New Rating Scale", href=f"/sessions/{id}/questions/new/rating", cls="button"),
                    cls="button-group"
                ),
                
                Div(
                    *[Div(
                        H4(q.title),
                        P(f"Type: {q.type.replace('_', ' ').title()}"),
                        P(Span("Active", cls="badge success") if q.active else Span("Inactive", cls="badge")),
                        Div(
                            Button(
                                "Toggle Status",
                                hx_post=f"/api/questions/{q.id}/toggle",
                                hx_swap="outerHTML",
                                hx_target=f"#question-{q.id}-actions"
                            ),
                            A("Edit", href=f"/questions/{q.id}/edit", cls="button"),
                            A("Results", href=f"/questions/{q.id}/results", cls="button primary"),
                            id=f"question-{q.id}-actions",
                            cls="actions"
                        ),
                        cls="question-card"
                    ) for q in session_questions] if session_questions else [P("No questions yet. Create your first question!")],
                    cls="question-grid"
                ),
                cls="section"
            ),
            
            Div(
                H3("Export"),
                P("Download session data including all questions and responses."),
                A("Export to CSV", href=f"/sessions/{id}/export", cls="button"),
                cls="section"
            ),
            
            title=f"Manage Session: {session_obj.name} - ClassPulse"
        )

    @rt("/api/sessions/{id}/toggle")
    def post(id: int):
        """Toggle session active status"""
        # Toggle status
        active = toggle_session_status(id)
        
        # Return updated button HTML
        return Div(
            Button(
                "Toggle Status", 
                hx_post=f"/api/sessions/{id}/toggle",
                hx_swap="outerHTML",
                hx_target="#session-actions"
            ),
            A("Present Mode", href=f"/present/{id}", cls="button primary"),
            id="session-actions",
            cls="actions"
        )

    @rt("/present/{id}")
    def get(id: int, session):
        """Presenter mode for a session"""
        user_id = session.get('user_id')
        
        # Get session and verify ownership
        session_obj = sessions[id]
        if not session_obj or session_obj.user_id != user_id:
            return RedirectResponse('/sessions', status_code=303)
        
        # Get questions for this session
        session_questions = get_session_questions(id)
        active_questions = [q for q in session_questions if q.active]
        
        # Create join URL and QR code
        join_url = f"{app.host_url}/audience/{session_obj.code}"
        qr_code = create_qr_code_data(join_url)
        
        return Titled(
            f"Presenting: {session_obj.name} - ClassPulse",
            Div(
                Div(
                    H1("ClassPulse", Span("", cls="logo")),
                    H2(f"Presenting: {session_obj.name}"),
                    Div(
                        A("Exit Presentation", href=f"/sessions/{id}", cls="button"),
                        cls="presenter-controls"
                    ),
                    cls="presenter-header"
                ),
                
                Div(
                    Div(
                        H3("Join Information"),
                        Div(
                            Div(
                                H4("Session Code"),
                                P(session_obj.code, cls="session-code"),
                                P(join_url),
                                cls="join-info"
                            ),
                            Div(
                                Img(src=qr_code, alt=f"QR Code for session {session_obj.code}"),
                                cls="qr-code"
                            ) if qr_code else None,
                            cls="join-container"
                        ),
                        cls="presenter-sidebar"
                    ),
                    
                    Div(
                        H3("Active Questions"),
                        Div(
                            *[Div(
                                H4(q.title),
                                P(f"Type: {q.type.replace('_', ' ').title()}"),
                                
                                # Real-time results container
                                Div(
                                    P("Loading results..."),
                                    id=f"results-{q.id}",
                                    cls="results-container",
                                    hx_ext="ws",
                                    ws_connect=f"/ws/results/{q.id}"
                                ),
                                
                                cls="question-display"
                            ) for q in active_questions] if active_questions else [
                                P("No active questions. Activate questions from the session management page.")
                            ],
                            cls="questions-list"
                        ),
                        cls="presenter-main"
                    ),
                    
                    cls="presenter-layout"
                ),
                
                cls="presenter-container"
            )
        )
    
    return rt

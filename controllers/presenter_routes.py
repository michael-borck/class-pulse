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
    def get(session, request=None):
        """Home/Dashboard page"""
        # Use the session parameter directly which should have auth from middleware
        from app import basic_auth
        
        # Apply our auth decorator
        @basic_auth
        def protected_dashboard(session, request=None):
            user_id = session.get('user_id')
            user = users[user_id]
            
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
        
        # Call the protected function with request
        return protected_dashboard(session, request=request)

    @rt("/sessions")
    def get(session, request=None):
        """List all sessions for the current user"""
        from app import basic_auth
        
        # Apply our auth decorator
        @basic_auth
        def protected_sessions_list(session, request=None):
            user_id = session.get('user_id')
            
            # Get all sessions for the user
            user_sessions = get_user_sessions(user_id)
            
            return layout(
                H2("Your Sessions"),
                
                Div(
                    A("Create New Session", href="/sessions/new", cls="button primary"),
                    A("Quick Create Session", href="/sessions/new?name=Quick+Session", cls="button"),
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
        
        # Call the protected function
        return protected_sessions_list(session, request=request)

    @rt("/sessions/new")
    def get(session=None, request=None, name: str = None):
        """Create new session form"""
        # Apply our auth decorator
        from app import basic_auth
        import logging
        logger = logging.getLogger("classpulse.presenter_routes")
        
        # Check if we have a name parameter (for quick creation)
        try:
            if name or (request and hasattr(request, 'query_params') and request.query_params.get('name')):
                quick_name = name or request.query_params.get('name')
                logger.info(f"Quick session create with name: {quick_name}")
                
                @basic_auth
                def create_quick_session(session, request=None):
                    user_id = session.get('user_id')
                    try:
                        # Create the session directly
                        new_session = create_session(user_id, quick_name)
                        logger.info(f"Quick created session with ID: {new_session.id}")
                        return RedirectResponse(f'/sessions/{new_session.id}', status_code=303)
                    except Exception as e:
                        logger.error(f"Failed to quick create session: {e}")
                        # Fall through to the form
                
                # Try quick creation, but fall through to form if it fails
                result = create_quick_session(session, request)
                if result:
                    return result
        except Exception as e:
            logger.error(f"Error in quick session creation: {e}")
            # Fall through to the form
        
        @basic_auth
        def protected_new_session(session, request=None):
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
                
                P(A("Quick Create Default Session", href="/sessions/new?name=Quick+Session")),
                
                title="New Session - ClassPulse"
            )
        
        # Call the protected function
        return protected_new_session(session, request=request)

    @rt("/sessions/new")
    def post(request, session=None):
        """Handle new session creation"""
        from app import basic_auth
        import logging
        logger = logging.getLogger("classpulse.presenter_routes")
        
        # Try to extract name from form data
        name = ""
        try:
            # Try various methods to get the name
            if hasattr(request, 'form') and hasattr(request.form, 'get'):
                name = request.form.get('name', '')
            
            # Or try to get it from the form dict
            if not name and hasattr(request, 'form'):
                if hasattr(request.form, '_dict'):
                    form_dict = request.form._dict
                    if 'name' in form_dict:
                        name = form_dict['name']
                elif hasattr(request.form, 'items'):
                    form_dict = dict(request.form.items())
                    if 'name' in form_dict:
                        name = form_dict['name']
            
            # Last resort - query params
            if not name and hasattr(request, 'query_params'):
                name = request.query_params.get('name', '')
                
            logger.info(f"Extracted session name: '{name}'")
        except Exception as e:
            logger.error(f"Error extracting session name: {e}")
            
        # Default name if none provided
        if not name:
            import datetime
            name = f"Session {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
            logger.info(f"Using default name: {name}")
        
        @basic_auth
        def protected_create_session(session, request=None):
            user_id = session.get('user_id')
            logger.info(f"Creating session with name '{name}' for user {user_id}")
            
            # Create the session
            try:
                new_session = create_session(user_id, name)
                logger.info(f"Created new session with ID: {new_session.id}")
                return RedirectResponse(f'/sessions/{new_session.id}', status_code=303)
            except Exception as e:
                logger.error(f"Failed to create session: {e}")
                # Emergency fallback - redirect to sessions list
                return RedirectResponse('/sessions', status_code=303)
        
        # Get the session from the request or parameter
        if hasattr(request, 'session'):
            return protected_create_session(request.session)
        else:
            return protected_create_session(session)

    @rt("/sessions/{id}")
    def get(id: int, session):
        """Session management page"""
        import logging
        logger = logging.getLogger("classpulse.presenter_routes")
        
        logger.info(f"Viewing session {id}")
        user_id = session.get('user_id')
        logger.info(f"User ID from session: {user_id}")
        
        # Get session and verify ownership
        try:
            session_id = int(id)  # Convert to int if string
            session_obj = sessions[session_id]
            logger.info(f"Found session: {session_obj.name} (User ID: {session_obj.user_id})")
            
            if not session_obj:
                logger.warning(f"Session {id} not found")
                return RedirectResponse('/sessions', status_code=303)
                
            # Emergency access for debug: always allow admin user
            admin_access = False
            if user_id == 1:  # Admin ID
                admin_access = True
                logger.info("Admin access granted")
            
            if not admin_access and session_obj.user_id != user_id:
                logger.warning(f"Session {id} belongs to user {session_obj.user_id}, not {user_id}")
                return RedirectResponse('/sessions', status_code=303)
            
            # Get questions for this session
            session_questions = get_session_questions(id)
            logger.info(f"Found {len(session_questions)} questions for session {id}")
            
            # Create join URL and QR code
            join_url = f"{app.host_url}/audience/{session_obj.code}"
            try:
                qr_code = create_qr_code_data(join_url)
                logger.info("QR code generated successfully")
            except Exception as e:
                logger.error(f"Error generating QR code: {e}")
                qr_code = None
                
        except Exception as e:
            logger.error(f"Error loading session {id}: {e}")
            return RedirectResponse('/sessions', status_code=303)
        
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

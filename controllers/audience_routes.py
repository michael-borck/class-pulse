from fasthtml.common import *
import json
import uuid
from datetime import datetime
from models.schema import sessions, Session, questions, Question, responses, Response
from utils.session_manager import (
    get_session_by_code, get_session_questions, record_response
)

def setup_audience_routes(rt):
    """
    Set up audience-related routes
    """
    
    @rt("/join")
    def get():
        """Join session page for audience"""
        return Titled(
            "Join Session - ClassPulse",
            Div(
                Div(
                    H1("ClassPulse", Span("", cls="logo")),
                    H2("Join a Session"),
                    Form(
                        Div(
                            Label("Session Code", For="code"),
                            Input(id="code", name="code", placeholder="Enter 6-digit code", required=True),
                            cls="form-group"
                        ),
                        Button("Join", type="submit", cls="button primary"),
                        method="post",
                        action="/join"
                    ),
                    P(A("Back to login", href="/login"), cls="mt-4"),
                    cls="join-form"
                ),
                cls="join-container"
            )
        )

    @rt("/join")
    def post(code: str, session):
        """Handle join form submission"""
        # Normalize code (uppercase, remove spaces)
        code = code.upper().strip()
        
        # Check if session exists
        session_obj = get_session_by_code(code)
        
        if session_obj and session_obj.active:
            # Generate a unique audience ID if not already set
            if 'audience_id' not in session:
                session['audience_id'] = str(uuid.uuid4())
            
            # Store the session code
            session['session_code'] = code
            session['session_id'] = session_obj.id
            
            return RedirectResponse(f'/audience/{code}', status_code=303)
        else:
            return Titled(
                "Join Failed - ClassPulse",
                Div(
                    Div(
                        H1("ClassPulse", Span("", cls="logo")),
                        H2("Join Failed"),
                        P("Invalid or inactive session code.", cls="error"),
                        Form(
                            Div(
                                Label("Session Code", For="code"),
                                Input(id="code", name="code", value=code, required=True),
                                cls="form-group"
                            ),
                            Button("Try Again", type="submit", cls="button primary"),
                            method="post",
                            action="/join"
                        ),
                        cls="join-form"
                    ),
                    cls="join-container"
                )
            )

    @rt("/audience/{code}")
    def get(code: str, session):
        """Audience view for answering questions"""
        # Check if valid session code
        session_obj = get_session_by_code(code)
        if not session_obj or not session_obj.active:
            return Titled(
                "Invalid Session - ClassPulse",
                Div(
                    H1("ClassPulse", Span("", cls="logo")),
                    H2("Invalid Session"),
                    P("The session code is invalid or the session is not active."),
                    A("Try Another Code", href="/join", cls="button"),
                    cls="centered-content"
                )
            )
        
        # Get active questions for this session
        session_questions = get_session_questions(session_obj.id)
        active_questions = [q for q in session_questions if q.active]
        
        # Ensure audience ID is set
        audience_id = session.get('audience_id', str(uuid.uuid4()))
        session['audience_id'] = audience_id
        
        # Get respondent's existing answers
        respondent_answers = {}
        for question in active_questions:
            responses_list = responses(where="question_id = ? AND respondent_id = ?", 
                                     where_args=[question.id, audience_id])
            if responses_list:
                respondent_answers[question.id] = responses_list[0].response_value
        
        return Titled(
            f"ClassPulse - {session_obj.name}",
            Div(
                H1("ClassPulse", Span("", cls="logo")),
                H2(session_obj.name),
                P(f"Session Code: {code}", cls="session-code-display"),
                
                Div(
                    *[Div(
                        H3(q.title),
                        
                        # Multiple choice question
                        Div(
                            Form(
                                *[Div(
                                    Input(
                                        type="radio",
                                        id=f"q{q.id}-opt-{i}",
                                        name=f"response-{q.id}",
                                        value=option,
                                        checked=(respondent_answers.get(q.id) == option)
                                    ),
                                    Label(option, For=f"q{q.id}-opt-{i}"),
                                    cls="radio-option"
                                ) for i, option in enumerate(json.loads(q.options))],
                                
                                Button(
                                    "Submit Answer",
                                    hx_post=f"/audience/respond/{q.id}",
                                    hx_swap="outerHTML",
                                    hx_target=f"#question-{q.id}"
                                ),
                                
                                id=f"question-{q.id}",
                                cls="question-form"
                            )
                        ) if q.type == 'multiple_choice' else None,
                        
                        # Word cloud question
                        Div(
                            Form(
                                Div(
                                    Label("Your response:", For=f"word-response-{q.id}"),
                                    Input(
                                        id=f"word-response-{q.id}",
                                        name=f"response-{q.id}",
                                        value=respondent_answers.get(q.id, ""),
                                        placeholder="Enter words separated by spaces"
                                    ),
                                    cls="form-group"
                                ),
                                
                                Button(
                                    "Submit Answer",
                                    hx_post=f"/audience/respond/{q.id}",
                                    hx_swap="outerHTML",
                                    hx_target=f"#question-{q.id}"
                                ),
                                
                                id=f"question-{q.id}",
                                cls="question-form"
                            )
                        ) if q.type == 'word_cloud' else None,
                        
                        # Rating question
                        Div(
                            Form(
                                Div(
                                    Div(
                                        *[Div(
                                            Input(
                                                type="radio",
                                                id=f"q{q.id}-rating-{i}",
                                                name=f"response-{q.id}",
                                                value=str(i),
                                                checked=(respondent_answers.get(q.id) == str(i))
                                            ),
                                            Label(str(i), For=f"q{q.id}-rating-{i}"),
                                            cls="rating-option"
                                        ) for i in range(1, int(json.loads(q.options).get('max_rating', 5)) + 1)],
                                        cls="rating-scale"
                                    ),
                                    cls="form-group"
                                ),
                                
                                Button(
                                    "Submit Rating",
                                    hx_post=f"/audience/respond/{q.id}",
                                    hx_swap="outerHTML",
                                    hx_target=f"#question-{q.id}"
                                ),
                                
                                id=f"question-{q.id}",
                                cls="question-form"
                            )
                        ) if q.type == 'rating' else None,
                        
                        cls="question-card"
                    ) for q in active_questions] if active_questions else [
                        P("No active questions currently. Please wait for the presenter to activate questions.")
                    ],
                    cls="questions-list"
                )
            )
        )
        
    @rt("/audience/respond/{question_id}")
    def post(question_id: int, session):
        """Handle audience response to a question"""
        # Get the question
        question = questions[question_id]
        if not question or not question.active:
            return "Question is not available"
        
        # Get audience ID
        audience_id = session.get('audience_id')
        if not audience_id:
            return "Session error, please rejoin"
        
        # Get response value based on question type
        param_name = f"response-{question_id}"
        response_value = ""
        
        if question.type == 'multiple_choice':
            response_value = request.form.get(param_name)
        elif question.type == 'word_cloud':
            response_value = request.form.get(param_name, "").strip()
        elif question.type == 'rating':
            response_value = request.form.get(param_name)
        
        # Record response
        if response_value:
            record_response(question_id, question.session_id, response_value, audience_id)
        
        # Return confirmation message
        return Div(
            P("Thank you! Your response has been recorded.", cls="response-confirmation"),
            id=f"question-{question_id}",
            cls="question-form"
        )
    
    return rt

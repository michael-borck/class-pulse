from fasthtml.common import *
from models.schema import users, User
from utils.auth import authenticate_user, register_user

def setup_auth_routes(rt):
    """
    Set up authentication related routes
    """
    
    @rt("/login")
    def get():
        """Login page"""
        return Titled(
            "Login - ClassPulse",
            Div(
                Div(
                    H1("ClassPulse", Span("", cls="logo")),
                    H2("Login"),
                    Form(
                        Div(
                            Label("Username", For="username"),
                            Input(id="username", name="username", required=True),
                            cls="form-group"
                        ),
                        Div(
                            Label("Password", For="password"),
                            Input(id="password", name="password", type="password", required=True),
                            cls="form-group"
                        ),
                        Button("Login", type="submit", cls="button primary"),
                        method="post",
                        action="/login"
                    ),
                    P(A("Join a session as audience", href="/join"), cls="mt-4"),
                    cls="login-form"
                ),
                cls="login-container"
            )
        )

    @rt("/login")
    def post(username: str, password: str, session):
        """Handle login form submission"""
        user = authenticate_user(username, password)
        
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['display_name'] = user.display_name
            return RedirectResponse('/', status_code=303)
        else:
            return Titled(
                "Login Failed - ClassPulse",
                Div(
                    Div(
                        H1("ClassPulse", Span("", cls="logo")),
                        H2("Login Failed"),
                        P("Invalid username or password.", cls="error"),
                        Form(
                            Div(
                                Label("Username", For="username"),
                                Input(id="username", name="username", value=username, required=True),
                                cls="form-group"
                            ),
                            Div(
                                Label("Password", For="password"),
                                Input(id="password", name="password", type="password", required=True),
                                cls="form-group"
                            ),
                            Button("Login", type="submit", cls="button primary"),
                            method="post",
                            action="/login"
                        ),
                        cls="login-form"
                    ),
                    cls="login-container"
                )
            )

    @rt("/logout")
    def get(session):
        """Log out user"""
        session.clear()
        return RedirectResponse('/login', status_code=303)
        
    return rt

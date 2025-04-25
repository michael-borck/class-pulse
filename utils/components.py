from fasthtml.common import *

def layout(*content, title="ClassPulse"):
    """Main layout component"""
    return Titled(
        title,
        Header(
            Div(
                H1("ClassPulse", A(Span("", cls="logo"), href="/")),
                Nav(
                    Ul(
                        Li(A("Dashboard", href="/")),
                        Li(A("Sessions", href="/sessions")),
                        Li(A("Logout", href="/logout")),
                    )
                ),
                cls="container"
            ),
            cls="navbar"
        ),
        Main(
            Div(*content, cls="container"),
            cls="content"
        ),
        Footer(
            Div(
                P("© 2025 ClassPulse - Real-time Audience Interaction"),
                cls="container"
            ),
            cls="footer"
        )
    )

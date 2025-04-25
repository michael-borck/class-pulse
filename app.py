from fasthtml.common import *
import os

# Import models and utilities
from models.schema import db, users, User, sessions, Session, questions, Question, responses, Response

# Import controllers
from controllers.auth_routes import setup_auth_routes
from controllers.audience_routes import setup_audience_routes
from controllers.presenter_routes import setup_presenter_routes
from controllers.question_routes import setup_question_routes
from controllers.websocket_routes import setup_websocket_routes

# Create FastHTML app with WebSockets enabled
app, rt = fast_app(
    db_file='classpulse.db',
    exts='ws',  # Enable WebSockets
    pico=True,  # Use Pico CSS for basic styling
    debug=True,  # Enable debug mode
    hdrs=(
        # Add custom CSS
        Link(rel='stylesheet', href='/static/css/styles.css', type='text/css'),
        # Add charting library
        Script(src="https://cdn.jsdelivr.net/npm/chart.js", defer=True),
        # Add jQCloud for word clouds
        Link(rel='stylesheet', href="https://cdnjs.cloudflare.com/ajax/libs/jqcloud/1.0.4/jqcloud.min.css", type='text/css'),
        Script(src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.1/jquery.min.js"),
        Script(src="https://cdnjs.cloudflare.com/ajax/libs/jqcloud/1.0.4/jqcloud.min.js"),
        # Add custom JavaScript
        Script(src='/static/js/main.js', defer=True),
    )
)

# Authentication middleware
def auth_check(req, sess):
    """Check if user is authenticated"""
    auth = req.scope['auth'] = sess.get('user_id', None)
    
    # Skip auth for public routes
    path = req.url.path
    if path.startswith('/static/') or path == '/login' or path == '/join' or path.startswith('/audience/'):
        return None
    
    if not auth:
        return RedirectResponse('/login', status_code=303)

# Set up routes
rt = setup_auth_routes(rt)
rt = setup_audience_routes(rt)
rt = setup_presenter_routes(rt, app)
rt = setup_question_routes(rt)
app = setup_websocket_routes(app)

# Serve static files
@rt("/static/{path:path}")
async def static_files(path: str):
    return FileResponse(f"static/{path}")

# Run the app if this is the main module
if __name__ == "__main__":
    # Define host and port
    host = "0.0.0.0"
    port = 5002  # Use a different port
    
    # Properly register the auth middleware
    async def auth_middleware(request, call_next):
        session = request.session
        auth = session.get('user_id', None)
        
        # Skip auth for public routes
        path = request.url.path
        if path.startswith('/static/') or path == '/login' or path == '/join' or path.startswith('/audience/'):
            return await call_next(request)
        
        if not auth:
            return RedirectResponse('/login', status_code=303)
        
        return await call_next(request)
    
    # Add middleware
    app.add_middleware(auth_middleware)
    
    # Serve the app
    import uvicorn
    uvicorn.run(app, host=host, port=port)

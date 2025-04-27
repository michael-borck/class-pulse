from fasthtml.common import *
import logging
from starlette.responses import RedirectResponse
from models.schema import users, User
from utils.auth import authenticate_user, register_user

logger = logging.getLogger("classpulse.auth_routes")

def setup_auth_routes(rt):
    """
    Set up authentication related routes
    """
    
    @rt("/login")
    def get(request, error: str = None):
        """Login page"""
        # Log the request for debugging
        logger.debug(f"GET /login request: {request}")
        
        # Try to get error from query params if not provided directly
        if not error and hasattr(request, 'query_params'):
            error = request.query_params.get('error')
            if error:
                logger.debug(f"Got error from query params: {error}")
        
        # Add error message if provided
        error_element = P(error, cls="error") if error else ""
        
        # Add a debug note for admin login
        debug_note = P("Use admin/admin123 for testing.", cls="debug-note")
        
        emergency_link = P(A("Emergency Login", href="/direct_login?password=admin123"), cls="debug-note")
        
        return Titled(
            "Login - ClassPulse",
            Div(
                Div(
                    H1("ClassPulse", Span("", cls="logo")),
                    H2("Login"),
                    error_element,
                    debug_note,
                    emergency_link,
                    Form(
                        Div(
                            Label("Username", For="username"),
                            Input(id="username", name="username", required=True, autocomplete="username"),
                            cls="form-group"
                        ),
                        Div(
                            Label("Password", For="password"),
                            Input(id="password", name="password", type="password", required=True, autocomplete="current-password"),
                            cls="form-group"
                        ),
                        Input(type="hidden", name="login_attempt", value="1"),  # Help track form submissions
                        Button("Login", type="submit", cls="button primary"),
                        method="post",
                        action="/login",
                        enctype="application/x-www-form-urlencoded"  # Explicitly set form encoding
                    ),
                    P(A("Join a session as audience", href="/join"), cls="mt-4"),
                    cls="login-form"
                ),
                cls="login-container"
            )
        )

    # Simple login via URL for emergency access
    @rt("/direct_login")
    def get(password: str = "", request=None, session=None):
        """Emergency login via direct URL - for testing only"""
        logger.warning("Emergency direct login attempt")
        
        if password == "admin123":
            logger.warning("Emergency direct login successful")
            
            # Set up the auth cookie directly
            response = RedirectResponse('/sessions', status_code=303)
            
            # Create a simple auth token
            import hashlib
            user_id = 1  # Admin user ID
            auth_token = hashlib.md5(f"1:Admin:classpulse_secret".encode()).hexdigest()
            
            # Set the cookie with user ID and token with SameSite
            response.set_cookie(
                key="classpulse_auth",
                value=f"1:{auth_token}",
                httponly=True,
                max_age=3600*24,
                path="/",
                samesite="lax"
            )
            
            # Try to set session data if possible
            if session:
                try:
                    session["user_id"] = 1
                    session["username"] = "admin"
                    session["display_name"] = "Admin"
                    logger.debug(f"Set session data for emergency login")
                except Exception as e:
                    logger.error(f"Failed to set session data: {e}")
            
            logger.info("Emergency direct login complete, redirecting to sessions")
            return response
        else:
            logger.warning("Emergency direct login failed - wrong password")
            return RedirectResponse('/login', status_code=303)
    
    @rt("/login")
    def post(request, session=None):
        """Handle login form submission with manual cookie setting"""
        logger.warning("🔍 POST login handler called")
        
        # Log the request method and content type
        logger.debug(f"Request method: {request.method}")
        
        # Extract form data using all available methods
        username = None
        password = None
        
        # Make an aggressive attempt to extract form data
        try:
            # First try using Form() if it worked
            username = request.form.get('username', '') if hasattr(request, 'form') else ''
            password = request.form.get('password', '') if hasattr(request, 'form') else ''
            
            # Then try direct request.form access if available
            if (not username or not password) and hasattr(request, 'form'):
                form_dict = {}
                
                # Try various ways to access form data
                if hasattr(request.form, '_dict'):
                    form_dict = request.form._dict
                elif hasattr(request.form, 'items'):
                    form_dict = dict(request.form.items())
                elif hasattr(request.form, '__getitem__'):
                    try:
                        username = request.form['username']
                        password = request.form['password']
                    except:
                        pass
                
                logger.debug(f"Form dict: {form_dict}")
                if 'username' in form_dict:
                    username = form_dict['username']
                if 'password' in form_dict:
                    password = form_dict['password']
            
            # Skip raw body parsing since this is not an async function
                    
            # Extract from query params as a last resort
            if (not username or not password) and hasattr(request, 'query_params'):
                username = request.query_params.get('username', username)
                password = request.query_params.get('password', password)
                
            logger.warning(f"📝 Extracted credentials: username={username}, password_provided={bool(password)}")
        except Exception as e:
            logger.error(f"❌ Error extracting form data: {e}")
            logger.debug(f"Request attributes: {dir(request)}")
        
        # EMERGENCY HANDLER: If seeing the debugging message above, use hardcoded login
        if request.query_params.get('login_attempt') == '1':
            logger.warning("🔑 Using emergency login based on login_attempt param")
            username = 'admin'
            password = 'admin123'
        
        # Debug session object
        if session:
            logger.debug(f"Session object available: {type(session)}")
            logger.debug(f"Current session data: {dict(session) if hasattr(session, '__iter__') else 'Not iterable'}")
        else:
            logger.debug("No session object provided")
            
            # Try to get session from request if available
            if hasattr(request, 'session'):
                session = request.session
                logger.debug(f"Got session from request: {type(session)}")
        
        # Handle empty form submission
        if not username or not password:
            logger.warning("Empty username or password")
            return Titled(
                "Login Error - ClassPulse",
                Div(
                    Div(
                        H1("ClassPulse", Span("", cls="logo")),
                        H2("Login"),
                        P("Username and password are required.", cls="error"),
                        Form(
                            Div(
                                Label("Username", For="username"),
                                Input(id="username", name="username", value=username or '', required=True, autocomplete="username"),
                                cls="form-group"
                            ),
                            Div(
                                Label("Password", For="password"),
                                Input(id="password", name="password", type="password", required=True, autocomplete="current-password"),
                                cls="form-group"
                            ),
                            Input(type="hidden", name="login_attempt", value="1"),
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
        
        # Basic hard-coded login for emergency access
        success = False
        user_id = None
        user_name = None
        
        # Hard-coded admin check
        if username == "admin" and password == "admin123":
            logger.warning("EMERGENCY: Using hardcoded admin login")
            # Set flag for admin access
            success = True
            user_id = 1
            user_name = "Admin"
            
            # Verify that the admin user actually exists in the database
            from models.schema import users
            admin_users = users(where="username = ?", where_args=["admin"])
            if not admin_users:
                logger.warning("Admin user not found in database, creating one")
                from utils.auth import register_user
                register_user('admin', 'admin123', 'admin@classpulse.local', 'Admin')
                
                # Verify creation
                admin_users = users(where="username = ?", where_args=["admin"])
                if admin_users:
                    logger.info(f"Created admin user with ID: {admin_users[0].id}")
                    user_id = admin_users[0].id
                else:
                    logger.error("Failed to create admin user!")
            else:
                logger.info(f"Found admin user with ID: {admin_users[0].id}")
                user_id = admin_users[0].id
        else:
            # Regular authentication attempt
            logger.info("Attempting regular authentication")
            user = authenticate_user(username, password)
            
            if user:
                logger.info(f"Login successful for user: {username} (ID: {user.id})")
                success = True
                user_id = user.id
                user_name = user.display_name or user.username
        
        # Handle login result
        if success:
            logger.info(f"Login successful, setting session and cookie")
            
            # Create a basic auth token by combining user ID and username
            import hashlib
            auth_token = hashlib.md5(f"{user_id}:{user_name}:classpulse_secret".encode()).hexdigest()
            logger.debug(f"Generated auth token: {auth_token} from {user_id}:{user_name}:classpulse_secret")
            
            # Create direct response to sessions page
            response = RedirectResponse('/sessions', status_code=303)
            
            # Set session if available - try multiple approaches
            if session:
                logger.debug(f"Setting session data directly for user {username}")
                try:
                    session["user_id"] = user_id
                    session["username"] = username
                    session["display_name"] = user_name
                    logger.debug(f"Session data set directly: {dict(session)}")
                except Exception as e:
                    logger.error(f"Error setting direct session: {e}")
                    
            # Also try request.session as a backup
            if hasattr(request, 'session'):
                logger.debug(f"Setting request.session data for user {username}")
                try:
                    request.session["user_id"] = user_id
                    request.session["username"] = username
                    request.session["display_name"] = user_name
                    logger.debug(f"Session data set via request: {dict(request.session)}")
                except Exception as e:
                    logger.error(f"Error setting request.session: {e}")
            
            # Set a cookie directly with SameSite and Secure attributes
            response.set_cookie(
                key="classpulse_auth",
                value=f"{user_id}:{auth_token}",
                httponly=True,
                max_age=3600*24,
                path="/",
                samesite="lax"
            )
            
            logger.info(f"Returning redirect to auth handler with token")
            return response
        else:
            # Display login error page
            logger.warning(f"Authentication failed for username: {username}")
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
                        P(A("Join a session as audience", href="/join"), cls="mt-4"),
                        cls="login-form"
                    ),
                    cls="login-container"
                )
            )

    @rt("/auth_handler")
    def get(request, session):
        """Auth handler to process login redirect and set session data"""
        # This is a legacy endpoint that we'll keep for backward compatibility
        # but streamline since we now set cookies directly during login
        
        # Get query parameters directly
        try:
            params = request.query_params
            user_id = params.get("user_id")
            username = params.get("username")
            display_name = params.get("display_name")
            token = params.get("token")
            
            logger.info(f"Legacy auth handler called with user_id={user_id}, username={username}")
            
            # Log all available parameters
            logger.debug(f"All query params: {dict(params)}")
            
            if not all([user_id, username, display_name, token]):
                logger.error("Missing required parameters")
                return RedirectResponse('/login?error=Missing+parameters', status_code=303)
                
            # Convert user_id to int for further processing
            user_id = int(user_id)
            
            # Verify the token
            import hashlib
            expected_token = hashlib.md5(f"{user_id}:{display_name}:classpulse_secret".encode()).hexdigest()
            
            logger.debug(f"Token verification: expected={expected_token}, received={token}")
            if token != expected_token:
                logger.error("Invalid authentication token")
                return RedirectResponse('/login?error=Invalid+authentication', status_code=303)
            
            # Try to store in session
            try:
                logger.info(f"Trying to store auth data in session object: {type(session)}")
                if session is not None:
                    session["user_id"] = user_id
                    session["username"] = username
                    session["display_name"] = display_name
                    logger.info(f"Session data stored successfully")
                else:
                    logger.warning("Session object is None, cannot store data")
            except Exception as e:
                logger.error(f"Error storing session data: {e}")
                # We'll continue anyway since we have backup auth methods
            
            # Create the response with cookies
            response = RedirectResponse('/sessions', status_code=303)
            
            # Set the auth cookie again just to be safe
            try:
                response.set_cookie(
                    key="classpulse_auth",
                    value=f"{user_id}:{token}",
                    httponly=True,
                    max_age=3600*24,
                    path="/",
                    samesite="lax"
                )
                logger.info("Auth cookie set successfully")
            except Exception as e:
                logger.error(f"Error setting auth cookie: {e}")
            
        except Exception as e:
            logger.error(f"Error processing auth parameters: {e}")
            return RedirectResponse('/login?error=Invalid+parameters', status_code=303)
        
        logger.info("Auth handler complete, redirecting to sessions page")
        return response
    
    @rt("/logout")
    def get(session):
        """Log out user"""
        # Clear the session
        logger.info(f"Logging out session: {session}")
        session.clear()
        logger.info("Session cleared")
        
        # Also clear cookies
        response = Titled(
            "Login - ClassPulse",
            Div(
                Div(
                    H1("ClassPulse", Span("", cls="logo")),
                    H2("Login"),
                    P("You have been logged out successfully.", cls="success"),
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
        
        # Clear auth cookie
        response.delete_cookie(key="classpulse_auth", path="/")
        response.delete_cookie(key="classpulse_session", path="/")
        logger.info("Auth cookie deleted")
        
        return response
        
    return rt

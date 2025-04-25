# ClassPulse Developer Guide

This guide is intended for developers who want to understand, modify, or extend the ClassPulse application. It provides detailed information about the codebase, key components, and how to implement common changes.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Project Structure](#project-structure)
3. [Key Components](#key-components)
4. [Database Schema](#database-schema)
5. [Authentication Flow](#authentication-flow)
6. [Session Management](#session-management)
7. [WebSocket Implementation](#websocket-implementation)
8. [Adding a New Question Type](#adding-a-new-question-type)
9. [Customizing Visualizations](#customizing-visualizations)
10. [Common Development Tasks](#common-development-tasks)
11. [Troubleshooting](#troubleshooting)

## Getting Started

### Development Environment Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd classpulse
   ```

2. **Create and activate a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install python-fasthtml
   ```

4. **Run the development server**
   ```bash
   python app.py
   ```

5. **Access the application**
   Open your browser and navigate to http://localhost:5002

### Development Workflow

1. Create a feature branch for your changes
2. Make your code changes
3. Test your changes locally
4. Create a pull request for review

## Project Structure

ClassPulse follows a modular structure:

```
~/projects/classpulse/
├── app.py                  # Main application entry point
├── models/
│   └── schema.py           # Database schema definitions
├── controllers/
│   ├── auth_routes.py      # Authentication routes
│   ├── audience_routes.py  # Audience participation routes
│   ├── presenter_routes.py # Presenter dashboard routes 
│   ├── question_routes.py  # Question management routes
│   └── websocket_routes.py # Real-time WebSocket routes
├── utils/
│   ├── auth.py             # Authentication utilities
│   ├── components.py       # Reusable UI components
│   ├── qrcode.py           # QR code generation
│   └── session_manager.py  # Session management utilities
├── static/
│   ├── css/
│   │   └── styles.css      # Custom styling
│   ├── js/
│   │   └── main.js         # JavaScript functionality
│   └── img/                # Image assets
└── templates/
    ├── audience/           # Audience view templates 
    └── presenter/          # Presenter view templates
```

## Key Components

### FastHTML Framework

ClassPulse uses the FastHTML framework, which is built on top of Starlette. FastHTML provides a convenient way to generate HTML using Python syntax.

Key concepts:
- HTML tags are represented as Python functions (e.g., `Div()`, `P()`)
- Route handlers are defined with the `@rt` decorator
- Components can be created as Python functions that return HTML elements

Example of a FastHTML component:
```python
def layout(*content, title="ClassPulse"):
    """Main layout component"""
    return Titled(
        title,
        Header(
            # Header content...
        ),
        Main(
            Div(*content, cls="container"),
            cls="content"
        ),
        Footer(
            # Footer content...
        )
    )
```

### Route Controllers

Route controllers are organized by feature area:

1. **auth_routes.py**: Handles login/logout functionality
2. **audience_routes.py**: Manages audience-facing views and responses
3. **presenter_routes.py**: Provides presenter dashboard and management
4. **question_routes.py**: Handles question creation and results
5. **websocket_routes.py**: Manages real-time updates

Each controller module follows a similar pattern:
- A main setup function that takes the route decorator (`rt`)
- Route handler functions for GET/POST requests
- Returns HTML content or redirects as appropriate

Example:
```python
def setup_auth_routes(rt):
    """Set up authentication related routes"""
    
    @rt("/login")
    def get():
        # Route implementation...
        
    @rt("/login")
    def post(username: str, password: str, session):
        # Route implementation...
        
    return rt
```

### Utility Modules

1. **auth.py**: Handles password hashing, user authentication
2. **components.py**: Provides reusable UI components
3. **qrcode.py**: Generates QR codes for session joining
4. **session_manager.py**: Manages sessions, questions, and responses

## Database Schema

ClassPulse uses SQLite with the FastLite ORM. Tables are defined in `models/schema.py`:

1. **users**: Stores presenter accounts
2. **sessions**: Stores presentation sessions
3. **questions**: Stores questions of different types
4. **responses**: Stores audience responses

Example query patterns:

```python
# Get a specific record by ID
user = users[user_id]

# Query with conditions
session_list = sessions(where="code = ?", where_args=[code])

# Insert a record
user = User(username="example", password_hash="hash", email="email")
users.insert(user)

# Update a record
user.display_name = "New Name"
users.update(user)
```

## Authentication Flow

1. **Login Process**:
   - User submits username/password to `/login` (POST)
   - `authenticate_user()` verifies credentials
   - On success, user ID is stored in session
   - User is redirected to dashboard

2. **Authentication Middleware**:
   - Checks for user_id in session
   - Allows public routes (/login, /join, /audience/*)
   - Redirects to login for protected routes if not authenticated

3. **Password Security**:
   - Passwords are hashed using PBKDF2 with salt
   - Verification compares hashed passwords

## Session Management

Sessions in ClassPulse refer to presentation sessions, not web sessions:

1. **Creation**:
   - Presenter creates a session with a name
   - System generates a unique 6-digit code
   - Session is associated with the creator

2. **Question Management**:
   - Presenter can add questions of different types
   - Questions can be activated/deactivated
   - Questions are ordered within the session

3. **Audience Joining**:
   - Audience members join using the session code
   - They receive a unique respondent ID (UUID)
   - They can view and answer active questions

## WebSocket Implementation

Real-time updates use WebSockets:

1. **Connection Setup**:
   - Presenter connects to `/ws/results/{question_id}`
   - Connection is stored in a dictionary by question ID

2. **Update Process**:
   - When responses arrive, stats are calculated
   - Updates are sent to all connections for that question
   - Updates include formatted HTML with result information

3. **Client-Side Handling**:
   - HTMX handles WebSocket connections and updates
   - Charts are re-rendered when data changes

## Adding a New Question Type

To add a new question type (e.g., "Ranking"):

1. **Update Schema**:
   - No schema change needed, as the `type` field is a string
   - Add a new creation function in `session_manager.py`:

   ```python
   def create_ranking_question(session_id: int, title: str, items: List[str]) -> Question:
       """Create a ranking question"""
       question = Question(
           session_id=session_id,
           type='ranking',
           title=title,
           options=json.dumps(items),
           active=True,
           created_at=datetime.now().isoformat(),
           order=0
       )
       
       return questions.insert(question)
   ```

2. **Add Result Processing**:
   - Add a function to process results in `session_manager.py`:

   ```python
   def get_ranking_results(question_id: int) -> Dict[str, Dict[str, int]]:
       """Get results for a ranking question"""
       # Implementation...
   ```

3. **Update Controllers**:
   - Add a new route in `question_routes.py` for creation
   - Extend `audience_routes.py` to handle the new question type
   - Update visualization in `questions/{id}/results`

4. **Add UI Components**:
   - Create audience interface for ranking questions
   - Add visualization code for ranking results

## Customizing Visualizations

Visualizations are handled through Chart.js:

1. **Chart Configuration**:
   - Chart options are in `question_routes.py` in the results route
   - Different configurations are used based on question type

2. **Customizing Charts**:
   - Modify the chart configuration in `question_routes.py`
   - Update the initialization code in `static/js/main.js`

Example for changing chart colors:
```javascript
new Chart(ctx, {
    type: chartType,
    data: chartData,
    options: {
        // ...existing options
        plugins: {
            legend: {
                labels: {
                    color: '#333'
                }
            }
        }
    }
});
```

## Common Development Tasks

### Adding a New Route

1. Choose the appropriate controller file
2. Add a route handler function:

```python
@rt("/my-new-route")
def get():
    return layout(
        H2("My New Page"),
        P("Page content here")
    )
```

3. If needed, add a POST handler:

```python
@rt("/my-new-route")
def post(param1: str, param2: int):
    # Process the submission
    return RedirectResponse("/some-page", status_code=303)
```

### Creating a New UI Component

Create a function that returns HTML elements:

```python
def my_component(title, content):
    return Div(
        H3(title),
        P(content),
        cls="my-component"
    )
```

Then use it in your routes:

```python
@rt("/some-route")
def get():
    return layout(
        my_component("Title 1", "Content 1"),
        my_component("Title 2", "Content 2")
    )
```

### Extending the Database Schema

To add a new table or field:

1. Update `models/schema.py`:

```python
# Add a new table
settings = db.t.settings
if settings not in db.t:
    settings.create(
        id=int,
        user_id=int,
        theme=str,
        notifications=bool,
        pk='id'
    )
Setting = settings.dataclass()
```

2. Add helper functions as needed in utility modules
3. Update controllers to use the new schema elements

## Troubleshooting

### Common Issues

1. **Database Errors**:
   - Check table creation in `schema.py`
   - Verify query parameters in function calls

2. **Route Errors**:
   - Ensure route decorators don't conflict
   - Check parameter types match between routes and inputs

3. **WebSocket Issues**:
   - Verify WebSocket connection setup
   - Check browser console for connection errors

### Development Tips

1. **Debug Mode**:
   - The application runs in debug mode by default
   - Error details are displayed in the console and browser

2. **Interactive Debugging**:
   - Add print statements for debugging
   - Use browser developer tools for frontend issues

3. **Database Inspection**:
   - Use SQLite tools to inspect the database directly:
   ```bash
   sqlite3 classpulse.db
   .tables
   SELECT * FROM users;
   ```

4. **Testing WebSockets**:
   - Test WebSocket connections with browser developer tools
   - Monitor the network tab for WebSocket frames

# ClassPulse API Reference

This document provides a comprehensive reference for all the API endpoints, functions, and utilities available in the ClassPulse application. Use this reference when working with the codebase.

## Table of Contents

- [HTTP Endpoints](#http-endpoints)
- [WebSocket Endpoints](#websocket-endpoints)
- [Database API](#database-api)
- [Authentication API](#authentication-api)
- [Session Management API](#session-management-api)
- [Utility Functions](#utility-functions)

## HTTP Endpoints

### Authentication Routes

#### Login Page
- **URL**: `/login`
- **Method**: `GET`
- **Controller**: `auth_routes.py`
- **Description**: Displays the login form
- **Response**: HTML login page

#### Process Login
- **URL**: `/login`
- **Method**: `POST`
- **Controller**: `auth_routes.py`
- **Parameters**: 
  - `username` (string): User's username
  - `password` (string): User's password
- **Description**: Authenticates a user
- **Response**: Redirects to dashboard on success, shows error on failure

#### Logout
- **URL**: `/logout`
- **Method**: `GET`
- **Controller**: `auth_routes.py`
- **Description**: Logs out the current user
- **Response**: Redirects to login page

### Presenter Routes

#### Dashboard
- **URL**: `/`
- **Method**: `GET`
- **Controller**: `presenter_routes.py`
- **Description**: Displays the presenter dashboard
- **Response**: HTML dashboard page with active sessions

#### Sessions List
- **URL**: `/sessions`
- **Method**: `GET`
- **Controller**: `presenter_routes.py`
- **Description**: Lists all sessions for the current user
- **Response**: HTML page with session list

#### New Session Form
- **URL**: `/sessions/new`
- **Method**: `GET`
- **Controller**: `presenter_routes.py`
- **Description**: Displays the new session form
- **Response**: HTML form for session creation

#### Create Session
- **URL**: `/sessions/new`
- **Method**: `POST`
- **Controller**: `presenter_routes.py`
- **Parameters**:
  - `name` (string): Session name
- **Description**: Creates a new session
- **Response**: Redirects to session management page

#### Session Management
- **URL**: `/sessions/{id}`
- **Method**: `GET`
- **Controller**: `presenter_routes.py`
- **Parameters**:
  - `id` (integer): Session ID
- **Description**: Displays the session management page
- **Response**: HTML page with session details and questions

#### Present Mode
- **URL**: `/present/{id}`
- **Method**: `GET`
- **Controller**: `presenter_routes.py`
- **Parameters**:
  - `id` (integer): Session ID
- **Description**: Displays the presenter view with real-time results
- **Response**: HTML page with real-time question results

### Question Routes

#### New Question Form
- **URL**: `/sessions/{session_id}/questions/new/{type}`
- **Method**: `GET`
- **Controller**: `question_routes.py`
- **Parameters**:
  - `session_id` (integer): Session ID
  - `type` (string): Question type (multiple_choice, word_cloud, rating)
- **Description**: Displays the form for creating a new question
- **Response**: HTML form for question creation

#### Create Multiple Choice Question
- **URL**: `/sessions/{session_id}/questions/new/multiple_choice`
- **Method**: `POST`
- **Controller**: `question_routes.py`
- **Parameters**:
  - `session_id` (integer): Session ID
  - `title` (string): Question title
  - `options` (string): Question options (newline-separated)
- **Description**: Creates a new multiple choice question
- **Response**: Redirects to session management page

#### Create Word Cloud Question
- **URL**: `/sessions/{session_id}/questions/new/word_cloud`
- **Method**: `POST`
- **Controller**: `question_routes.py`
- **Parameters**:
  - `session_id` (integer): Session ID
  - `title` (string): Question title
- **Description**: Creates a new word cloud question
- **Response**: Redirects to session management page

#### Create Rating Question
- **URL**: `/sessions/{session_id}/questions/new/rating`
- **Method**: `POST`
- **Controller**: `question_routes.py`
- **Parameters**:
  - `session_id` (integer): Session ID
  - `title` (string): Question title
  - `max_rating` (integer): Maximum rating value (default: 5)
- **Description**: Creates a new rating question
- **Response**: Redirects to session management page

#### Question Results
- **URL**: `/questions/{id}/results`
- **Method**: `GET`
- **Controller**: `question_routes.py`
- **Parameters**:
  - `id` (integer): Question ID
- **Description**: Displays the question results with visualizations
- **Response**: HTML page with result visualizations

#### Export Question Results
- **URL**: `/questions/{id}/export`
- **Method**: `GET`
- **Controller**: `question_routes.py`
- **Parameters**:
  - `id` (integer): Question ID
- **Description**: Exports question results as CSV
- **Response**: CSV file download

#### Export Session Results
- **URL**: `/sessions/{id}/export`
- **Method**: `GET`
- **Controller**: `question_routes.py`
- **Parameters**:
  - `id` (integer): Session ID
- **Description**: Exports all session results as CSV
- **Response**: CSV file download

### Audience Routes

#### Join Form
- **URL**: `/join`
- **Method**: `GET`
- **Controller**: `audience_routes.py`
- **Description**: Displays the session join form
- **Response**: HTML join form

#### Process Join
- **URL**: `/join`
- **Method**: `POST`
- **Controller**: `audience_routes.py`
- **Parameters**:
  - `code` (string): Session code
- **Description**: Processes a join request
- **Response**: Redirects to audience view on success, shows error on failure

#### Audience View
- **URL**: `/audience/{code}`
- **Method**: `GET`
- **Controller**: `audience_routes.py`
- **Parameters**:
  - `code` (string): Session code
- **Description**: Displays the audience view with active questions
- **Response**: HTML page with question forms

#### Submit Response
- **URL**: `/audience/respond/{question_id}`
- **Method**: `POST`
- **Controller**: `audience_routes.py`
- **Parameters**:
  - `question_id` (integer): Question ID
  - `response-{question_id}` (string): Response value
- **Description**: Submits a response to a question
- **Response**: HTML confirmation message

### API Endpoints

#### Toggle Session Status
- **URL**: `/api/sessions/{id}/toggle`
- **Method**: `POST`
- **Controller**: `presenter_routes.py`
- **Parameters**:
  - `id` (integer): Session ID
- **Description**: Toggles a session's active status
- **Response**: HTML for updated button

#### Toggle Question Status
- **URL**: `/api/questions/{id}/toggle`
- **Method**: `POST`
- **Controller**: `question_routes.py`
- **Parameters**:
  - `id` (integer): Question ID
- **Description**: Toggles a question's active status
- **Response**: HTML for updated button

### Static Files
- **URL**: `/static/{path}`
- **Method**: `GET`
- **Controller**: `app.py`
- **Parameters**:
  - `path` (string): File path
- **Description**: Serves static files (CSS, JS, images)
- **Response**: Requested file

## WebSocket Endpoints

#### Question Results WebSocket
- **URL**: `/ws/results/{question_id}`
- **Controller**: `websocket_routes.py`
- **Parameters**:
  - `question_id` (integer): Question ID
- **Description**: Provides real-time updates for question results
- **Messages**: HTML content with updated results
- **Update Frequency**: Every 2 seconds
- **Example Usage**:
  ```html
  <div id="results-container" 
       hx_ext="ws" 
       ws_connect="/ws/results/123">
    Loading results...
  </div>
  ```

## Database API

### Tables

#### users
- **Fields**:
  - `id` (integer): Primary key
  - `username` (string): Unique username
  - `password_hash` (string): Hashed password with salt
  - `email` (string): User email
  - `display_name` (string): Display name

#### sessions
- **Fields**:
  - `id` (integer): Primary key
  - `code` (string): Unique 6-digit join code
  - `name` (string): Session name
  - `created_at` (string): ISO timestamp
  - `user_id` (integer): Foreign key to users.id
  - `active` (boolean): Session active status

#### questions
- **Fields**:
  - `id` (integer): Primary key
  - `session_id` (integer): Foreign key to sessions.id
  - `type` (string): Question type
  - `title` (string): Question title
  - `options` (string): JSON string with options
  - `active` (boolean): Question active status
  - `created_at` (string): ISO timestamp
  - `order` (integer): Display order

#### responses
- **Fields**:
  - `id` (integer): Primary key
  - `question_id` (integer): Foreign key to questions.id
  - `session_id` (integer): Foreign key to sessions.id
  - `response_value` (string): Response content
  - `respondent_id` (string): Anonymous UUID
  - `created_at` (string): ISO timestamp

### Query Methods

#### Get by ID
```python
# Get a record by primary key
user = users[user_id]
```

#### Query with Conditions
```python
# Query with WHERE clause
results = users(where="username = ?", where_args=["admin"])
```

#### Insert Record
```python
# Create and insert a record
user = User(username="alice", password_hash="hash", email="email@example.com")
users.insert(user)
```

#### Update Record
```python
# Update a record
user.display_name = "New Name"
users.update(user)
```

#### Delete Record
```python
# Delete a record by ID
users.delete(user_id)
```

## Authentication API

### Functions

#### hash_password
```python
def hash_password(password, salt=None)
```
- **Description**: Hashes a password with PBKDF2 and salt
- **Parameters**:
  - `password` (string): Password to hash
  - `salt` (string, optional): Salt to use (generates one if not provided)
- **Returns**: String with format "salt$hash"

#### verify_password
```python
def verify_password(stored_password, provided_password)
```
- **Description**: Verifies a password against a stored hash
- **Parameters**:
  - `stored_password` (string): Stored password hash with salt
  - `provided_password` (string): Password to verify
- **Returns**: Boolean indicating if password matches

#### register_user
```python
def register_user(username, password, email, display_name=None)
```
- **Description**: Registers a new user
- **Parameters**:
  - `username` (string): Username
  - `password` (string): Password
  - `email` (string): Email address
  - `display_name` (string, optional): Display name
- **Returns**: Tuple (success, message)

#### authenticate_user
```python
def authenticate_user(username, password)
```
- **Description**: Authenticates a user
- **Parameters**:
  - `username` (string): Username
  - `password` (string): Password
- **Returns**: User object if successful, None otherwise

## Session Management API

### Functions

#### create_session
```python
def create_session(user_id, name)
```
- **Description**: Creates a new session
- **Parameters**:
  - `user_id` (integer): User ID
  - `name` (string): Session name
- **Returns**: Session object

#### get_session_by_code
```python
def get_session_by_code(code)
```
- **Description**: Gets a session by its code
- **Parameters**:
  - `code` (string): Session code
- **Returns**: Session object or None

#### get_user_sessions
```python
def get_user_sessions(user_id)
```
- **Description**: Gets all sessions for a user
- **Parameters**:
  - `user_id` (integer): User ID
- **Returns**: List of Session objects

#### toggle_session_status
```python
def toggle_session_status(session_id)
```
- **Description**: Toggles a session's active status
- **Parameters**:
  - `session_id` (integer): Session ID
- **Returns**: New active status (boolean)

#### create_multiple_choice_question
```python
def create_multiple_choice_question(session_id, title, options, order=0)
```
- **Description**: Creates a multiple choice question
- **Parameters**:
  - `session_id` (integer): Session ID
  - `title` (string): Question title
  - `options` (list): List of options
  - `order` (integer, optional): Display order
- **Returns**: Question object

#### create_word_cloud_question
```python
def create_word_cloud_question(session_id, title, order=0)
```
- **Description**: Creates a word cloud question
- **Parameters**:
  - `session_id` (integer): Session ID
  - `title` (string): Question title
  - `order` (integer, optional): Display order
- **Returns**: Question object

#### create_rating_question
```python
def create_rating_question(session_id, title, max_rating=5, order=0)
```
- **Description**: Creates a rating question
- **Parameters**:
  - `session_id` (integer): Session ID
  - `title` (string): Question title
  - `max_rating` (integer, optional): Maximum rating value
  - `order` (integer, optional): Display order
- **Returns**: Question object

#### get_session_questions
```python
def get_session_questions(session_id)
```
- **Description**: Gets all questions for a session
- **Parameters**:
  - `session_id` (integer): Session ID
- **Returns**: List of Question objects

#### toggle_question_status
```python
def toggle_question_status(question_id)
```
- **Description**: Toggles a question's active status
- **Parameters**:
  - `question_id` (integer): Question ID
- **Returns**: New active status (boolean)

#### record_response
```python
def record_response(question_id, session_id, value, respondent_id)
```
- **Description**: Records a response to a question
- **Parameters**:
  - `question_id` (integer): Question ID
  - `session_id` (integer): Session ID
  - `value` (string): Response value
  - `respondent_id` (string): Respondent ID
- **Returns**: Response object

#### get_question_stats
```python
def get_question_stats(question_id)
```
- **Description**: Gets statistics for a question
- **Parameters**:
  - `question_id` (integer): Question ID
- **Returns**: Dictionary with question statistics

## Utility Functions

### QR Code Generation

#### create_qr_code_data
```python
def create_qr_code_data(url, size=200)
```
- **Description**: Creates a QR code data URL for a given URL
- **Parameters**:
  - `url` (string): URL to encode
  - `size` (integer, optional): QR code size in pixels
- **Returns**: Data URL string or None on failure

### UI Components

#### layout
```python
def layout(*content, title="ClassPulse")
```
- **Description**: Creates the main layout template
- **Parameters**:
  - `*content`: Content to include in the main area
  - `title` (string, optional): Page title
- **Returns**: HTML for the complete page

### Session Helpers

#### generate_session_code
```python
def generate_session_code(length=6)
```
- **Description**: Generates a random alphanumeric code
- **Parameters**:
  - `length` (integer, optional): Code length
- **Returns**: Random code string

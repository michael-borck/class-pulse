# ClassPulse Technical Specification

## 1. Introduction

ClassPulse is a real-time audience interaction system designed for presenters to engage their audience through interactive questions and visualize responses in real-time.

### 1.1 Purpose

This document defines the technical specifications for ClassPulse, including functional requirements, data models, APIs, and user interfaces.

### 1.2 Scope

ClassPulse enables presenters to:
- Create interactive sessions with unique join codes
- Add different types of questions (multiple choice, word cloud, rating scale)
- View real-time responses through visualizations
- Export results for analysis

Audience members can:
- Join sessions using a code or QR scan
- Respond to active questions
- See confirmation of submitted responses

## 2. Functional Requirements

### 2.1 Authentication System

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| AUTH-1 | System shall provide login functionality for presenters | High |
| AUTH-2 | System shall support password hashing for security | High |
| AUTH-3 | System shall provide session-based authentication | High |
| AUTH-4 | System shall redirect unauthenticated users to login page | High |
| AUTH-5 | System shall support anonymous access for audience members | High |

### 2.2 Session Management

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| SESS-1 | System shall generate unique 6-digit session codes | High |
| SESS-2 | System shall support session activation/deactivation | Medium |
| SESS-3 | System shall associate sessions with creator | High |
| SESS-4 | System shall generate QR codes for session joining | Medium |
| SESS-5 | System shall list all sessions for a presenter | Medium |

### 2.3 Question Management

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| QUES-1 | System shall support multiple choice questions | High |
| QUES-2 | System shall support word cloud questions | High |
| QUES-3 | System shall support rating scale questions | High |
| QUES-4 | System shall allow questions to be activated/deactivated | Medium |
| QUES-5 | System shall store question configuration (options, max ratings) | High |

### 2.4 Response Collection

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| RESP-1 | System shall collect and store audience responses | High |
| RESP-2 | System shall associate responses with respondent IDs | High |
| RESP-3 | System shall update response if respondent submits again | Medium |
| RESP-4 | System shall validate responses against question type | Medium |
| RESP-5 | System shall provide confirmation on submission | Medium |

### 2.5 Real-time Updates

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REAL-1 | System shall update presenters in real-time as responses arrive | High |
| REAL-2 | System shall use WebSockets for real-time communication | High |
| REAL-3 | System shall handle connection management gracefully | Medium |
| REAL-4 | System shall update visualizations without page reload | High |

### 2.6 Data Export

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| EXP-1 | System shall allow export of individual question results | Medium |
| EXP-2 | System shall allow export of entire session data | Medium |
| EXP-3 | System shall export data in CSV format | Medium |

## 3. Data Models

### 3.1 User

| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Primary key |
| username | String | Unique username |
| password_hash | String | Hashed password with salt |
| email | String | User email |
| display_name | String | Display name for UI |

### 3.2 Session

| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Primary key |
| code | String | Unique 6-digit join code |
| name | String | Session name |
| created_at | String | ISO timestamp of creation |
| user_id | Integer | Foreign key to User |
| active | Boolean | Session active status |

### 3.3 Question

| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Primary key |
| session_id | Integer | Foreign key to Session |
| type | String | Question type (multiple_choice, word_cloud, rating) |
| title | String | Question text |
| options | String | JSON string of options or configuration |
| active | Boolean | Question active status |
| created_at | String | ISO timestamp of creation |
| order | Integer | Display order in session |

### 3.4 Response

| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Primary key |
| question_id | Integer | Foreign key to Question |
| session_id | Integer | Foreign key to Session |
| response_value | String | Response content |
| respondent_id | String | Anonymous UUID for audience member |
| created_at | String | ISO timestamp of response |

## 4. API Endpoints

### 4.1 Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| /login | GET | Show login page |
| /login | POST | Process login credentials |
| /logout | GET | Log out current user |

### 4.2 Presenter Routes

| Endpoint | Method | Description |
|----------|--------|-------------|
| / | GET | Dashboard with active sessions |
| /sessions | GET | List all sessions |
| /sessions/new | GET | Form to create new session |
| /sessions/new | POST | Create a new session |
| /sessions/{id} | GET | Manage specific session |
| /present/{id} | GET | Present mode for session |

### 4.3 Question Routes

| Endpoint | Method | Description |
|----------|--------|-------------|
| /sessions/{session_id}/questions/new/{type} | GET | Form for new question |
| /sessions/{session_id}/questions/new/{type} | POST | Create new question |
| /questions/{id}/results | GET | View question results |
| /questions/{id}/export | GET | Export question results as CSV |
| /sessions/{id}/export | GET | Export session results as CSV |

### 4.4 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/sessions/{id}/toggle | POST | Toggle session status |
| /api/questions/{id}/toggle | POST | Toggle question status |

### 4.5 Audience Routes

| Endpoint | Method | Description |
|----------|--------|-------------|
| /join | GET | Show join form |
| /join | POST | Process join request |
| /audience/{code} | GET | Audience view for answering |
| /audience/respond/{question_id} | POST | Submit response |

### 4.6 WebSocket Endpoints

| Endpoint | Description |
|----------|-------------|
| /ws/results/{question_id} | Real-time updates for question results |

## 5. User Interface Specifications

### 5.1 Layout and Components

- Main layout with header, content area, and footer
- Responsive design for mobile and desktop
- Consistent styling and color scheme

### 5.2 Presenter Interfaces

- Dashboard with session cards
- Session management with question list
- Present mode with real-time results
- Result visualizations based on question type

### 5.3 Audience Interfaces

- Simple join page with code input
- Question display based on type
- Confirmation messages after submission

### 5.4 Visualizations

- Bar charts for multiple choice questions
- Word clouds for word cloud questions
- Bar charts for rating scales

## 6. Non-Functional Requirements

### 6.1 Performance

- Response time < 500ms for standard operations
- Real-time updates within 2 seconds of submission
- Support for at least 100 concurrent audience members

### 6.2 Security

- Password hashing with PBKDF2
- Session-based authentication
- Input validation and sanitization

### 6.3 Reliability

- Graceful handling of disconnections
- Data persistence for responses
- Error handling for all operations

### 6.4 Compatibility

- Support for modern browsers (Chrome, Firefox, Safari, Edge)
- Responsive design for mobile devices

## 7. Implementation Details

### 7.1 Technology Stack

- Backend: Python with FastHTML framework
- Frontend: HTML, CSS, JavaScript
- Database: SQLite with FastLite ORM
- Real-time: WebSockets
- Visualizations: Chart.js and jQCloud

### 7.2 Directory Structure

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

## 8. Testing Strategy

### 8.1 Unit Testing

- Test utility functions for auth, session management
- Test database operations and queries
- Test API endpoints

### 8.2 Integration Testing

- Test workflows (create session, add questions, join, respond)
- Test WebSocket communication
- Test data consistency across components

### 8.3 User Acceptance Testing

- Test with actual presenters and audience scenarios
- Verify real-time updates work as expected
- Validate visualization accuracy

## 9. Deployment Considerations

### 9.1 Development Environment

- Local development with SQLite database
- Development server on port 5002

### 9.2 Production Deployment

- Consider using PostgreSQL for larger deployments
- Deploy with Gunicorn and Nginx
- Implement proper logging and monitoring
- Consider containerization with Docker

## 10. Future Enhancements

### 10.1 Potential Features

- Additional question types (open-ended, polls)
- User registration system
- Theme customization
- Timer functionality for questions
- More visualization options
- Integration with LMS platforms

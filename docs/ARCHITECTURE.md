# ClassPulse System Architecture

## Overview

ClassPulse is a real-time audience interaction platform that allows presenters to engage with their audience through interactive questions. The system follows a modular architecture with clear separation of concerns, built using the FastHTML framework.

## System Components

### 1. Core Components

```
+-------------------+      +------------------+      +----------------+
|                   |      |                  |      |                |
|  Web Frontend     |<---->|  Backend Server  |<---->|  Database      |
|  (HTML/CSS/JS)    |      |  (FastHTML/Python)|     |  (SQLite)      |
|                   |      |                  |      |                |
+-------------------+      +------------------+      +----------------+
           ^                        ^
           |                        |
           v                        v
+-------------------+      +------------------+
|                   |      |                  |
|  WebSocket        |<---->|  Real-time       |
|  Communication    |      |  Events          |
|                   |      |                  |
+-------------------+      +------------------+
```

### 2. Architectural Patterns

ClassPulse employs several architectural patterns:

1. **Model-View-Controller (MVC)**
   - **Models**: Database schema and data access layer
   - **Views**: HTML templates and FastHTML components
   - **Controllers**: Route handlers that process requests

2. **Service-Oriented Architecture**
   - Modular utilities that provide specific services
   - Clear interfaces between components

3. **Real-time Event Processing**
   - WebSocket connections for live updates
   - Event-driven architecture for question responses

## Data Flow

```
  +----------------+        +-----------------+       +------------------+
  |                |        |                 |       |                  |
  | Audience Member|------->| Join Session    |------>| View Questions   |
  |                |        |                 |       |                  |
  +----------------+        +-----------------+       +------------------+
                                                             |
                                                             v
  +----------------+        +-----------------+       +------------------+
  |                |        |                 |       |                  |
  | Presenter      |<-------| Real-time       |<------| Submit Responses |
  |                |        | Results Update  |       |                  |
  +----------------+        +-----------------+       +------------------+
        |
        v
  +----------------+
  |                |
  | Export Results |
  |                |
  +----------------+
```

## Module Breakdown

### Frontend Layer

1. **Static Assets**
   - CSS: Custom styling and layouts
   - JavaScript: Client-side interactivity and chart rendering
   - Images: Icons and visual elements

2. **Templates**
   - Presenter views: Dashboard, session management, results
   - Audience views: Join page, question answering interfaces

### Backend Layer

1. **Controllers**
   - `auth_routes.py`: Authentication and user management
   - `audience_routes.py`: Audience-facing interfaces
   - `presenter_routes.py`: Presenter dashboard and management
   - `question_routes.py`: Question creation and result display
   - `websocket_routes.py`: Real-time communication

2. **Utils**
   - `auth.py`: Authentication helpers and security
   - `components.py`: Reusable UI components
   - `qrcode.py`: QR code generation for easy session joining
   - `session_manager.py`: Session and question management logic

3. **Models**
   - `schema.py`: Database tables, relationships, and data models

### Database Schema

```
+----------------+       +----------------+       +----------------+
| Users          |       | Sessions       |       | Questions      |
+----------------+       +----------------+       +----------------+
| id             |<----->| id             |<----->| id             |
| username       |       | code           |       | session_id     |
| password_hash  |       | name           |       | type           |
| email          |       | created_at     |       | title          |
| display_name   |       | user_id        |       | options        |
+----------------+       | active         |       | active         |
                         +----------------+       | created_at     |
                                                  | order          |
                                                  +----------------+
                                                          |
                                                          v
                                                  +----------------+
                                                  | Responses      |
                                                  +----------------+
                                                  | id             |
                                                  | question_id    |
                                                  | session_id     |
                                                  | response_value |
                                                  | respondent_id  |
                                                  | created_at     |
                                                  +----------------+
```

## Technology Stack

1. **Backend**
   - Python 3.x
   - FastHTML framework (Based on Starlette)
   - Uvicorn ASGI server
   - FastLite (SQLite ORM)

2. **Frontend**
   - HTML/CSS
   - Vanilla JavaScript
   - Chart.js for data visualization
   - jQCloud for word cloud rendering

3. **Data Storage**
   - SQLite database

4. **Real-time Communication**
   - WebSockets for live updates

## Security Considerations

1. **Authentication**
   - Password hashing with salt using PBKDF2
   - Session-based authentication

2. **Data Protection**
   - Anonymous audience responses
   - Session ownership verification
   - Input validation and sanitization

3. **Access Control**
   - Route protection via middleware
   - Session-based authorization

## Scalability Considerations

The current architecture can handle small to medium-sized classrooms or presentation scenarios. For larger deployments, consider:

1. **Database Scaling**
   - Migrate from SQLite to PostgreSQL or MySQL
   - Implement connection pooling

2. **Performance Optimization**
   - Implement caching for frequent queries
   - Optimize WebSocket connections for high concurrency

3. **Deployment Options**
   - Containerize with Docker
   - Deploy with Gunicorn workers behind Nginx

# ClassPulse Data Flow

This document describes how data flows through the ClassPulse system, from creation to visualization. Understanding these flows helps developers follow the execution path through the codebase.

## Session Creation Flow

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │             │      │             │
│  Presenter  │──────▶  sessions/  │──────▶  create_    │──────▶  Database   │
│             │      │  new route  │      │  session()  │      │  (sessions) │
│             │      │             │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘      └─────────────┘
                                                                      │
                                                                      │
                                                                      ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │             │      │             │
│  Session    │◀─────│  sessions/  │◀─────│  get_user_  │◀─────│  Redirect   │
│  Management │      │  {id} route │      │  sessions() │      │  Response   │
│             │      │             │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘      └─────────────┘
```

## Question Creation Flow

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │             │
│  Presenter  │──────▶  /sessions/ │──────▶  Question   │
│             │      │  {id} page  │      │  Form Page  │
│             │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘
                                                │
                                                │
                                                ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │             │
│  Creation   │◀─────│  create_X_  │◀─────│  Form       │
│  in Database│      │  question() │      │  Submission │
│             │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘
```

## Audience Join Flow

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │             │      │             │
│  Audience   │──────▶  /join      │──────▶  get_session│──────▶  Validate   │
│  Member     │      │  page       │      │  _by_code() │      │  Code       │
│             │      │             │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘      └─────────────┘
                                                                      │
                                                                      │
                                                                      ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │             │      │             │
│  Question   │◀─────│  /audience/ │◀─────│  Generate   │◀─────│  Store in   │
│  Display    │      │  {code}     │      │  UUID       │      │  Session    │
│             │      │             │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘      └─────────────┘
```

## Response Submission Flow

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │             │
│  Audience   │──────▶  Form       │──────▶  /audience/ │
│  Member     │      │  Submission │      │  respond/{id}│
│             │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘
                                                │
                                                │
                                                ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │             │
│  Store in   │◀─────│  record_    │◀─────│  Extract    │
│  Database   │      │  response() │      │  Data       │
│             │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘
                            │
                            │
                            ▼
┌─────────────────────────────────────────┐
│                                         │
│  WebSocket Event (Notification to       │
│  connected presenters for this question)│
│                                         │
└─────────────────────────────────────────┘
```

## Real-time Results Flow

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │             │
│  Presenter  │──────▶  /present/  │──────▶  WebSocket  │
│             │      │  {id}       │      │  Connection │
│             │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘
                                                │
                                                │
                                                ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │             │
│  Results    │◀─────│  /ws/results│◀─────│  Periodic   │
│  Display    │      │  /{id}      │      │  Updates    │
│             │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘
                                                │
                                                │
                                                ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │             │
│  Chart.js   │◀─────│  Update     │◀─────│  get_question│
│  Rendering  │      │  HTML/Data  │      │  _stats()   │
│             │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘
```

## Results Export Flow

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │             │
│  Presenter  │──────▶  /questions/│──────▶  Query      │
│             │      │  {id}/export│      │  Responses  │
│             │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘
                                                │
                                                │
                                                ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │             │
│  CSV File   │◀─────│  Format as  │◀─────│  Process    │
│  Download   │      │  CSV        │      │  Data       │
│             │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘
```

## Authentication Flow

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │             │
│  User       │──────▶  /login     │──────▶  authenticate│
│             │      │  (POST)     │      │  _user()    │
│             │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘
                                                │
                                                │
                                                ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │ Success:    │
│  User       │◀─────│  Response   │◀─────│ Store in    │
│  Browser    │      │             │      │ Session     │
│             │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘
                                                │
                                                │
                                                ▼
                                          ┌─────────────┐
                                          │             │
                                          │  Redirect   │
                                          │  to Home    │
                                          │             │
                                          └─────────────┘
```

## Session Toggle Flow

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │             │
│  Presenter  │──────▶  "Toggle"   │──────▶  HTMX       │
│             │      │  Button     │      │  Request    │
│             │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘
                                                │
                                                │
                                                ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│             │      │             │      │             │
│  Update UI  │◀─────│  Return     │◀─────│  toggle_    │
│  Element    │      │  New HTML   │      │  session_   │
│             │      │             │      │  status()   │
└─────────────┘      └─────────────┘      └─────────────┘
```

## Data Model Relationships

```
┌───────────────────┐       ┌───────────────────┐
│                   │       │                   │
│  User             │       │  Session          │
│  ---------------  │       │  ---------------  │
│  id               │       │  id               │
│  username         │       │  code             │
│  password_hash    │       │  name             │
│  email            │       │  created_at       │
│  display_name     │       │  user_id ◀────────┼───────┐
│                   │       │  active           │       │
└───────────────────┘       └───────────────────┘       │
                                    │                    │
                                    │                    │
                                    ▼                    │
                            ┌───────────────────┐        │
                            │                   │        │
                            │  Question         │        │
                            │  ---------------  │        │
                            │  id               │        │
                            │  session_id ◀─────┼────────┘
                            │  type             │
                            │  title            │
                            │  options          │
                            │  active           │
                            │  created_at       │
                            │  order            │
                            └───────────────────┘
                                    │
                                    │
                                    ▼
                            ┌───────────────────┐
                            │                   │
                            │  Response         │
                            │  ---------------  │
                            │  id               │
                            │  question_id ◀────┼────────┐
                            │  session_id ◀─────┼────────┼─┐
                            │  response_value   │        │ │
                            │  respondent_id    │        │ │
                            │  created_at       │        │ │
                            └───────────────────┘        │ │
                                                         │ │
                            ┌───────────────────┐        │ │
                            │                   │        │ │
                            │  Legend           │        │ │
                            │  ---------------  │        │ │
                            │  → Foreign Key    │◀───────┘ │
                            │  relationship     │          │
                            │                   │◀─────────┘
                            └───────────────────┘
```

## Developer Notes

1. The diagrams above illustrate the primary data flows in the ClassPulse application. These are simplified representations to help developers understand the codebase structure.

2. The actual implementation may contain additional steps, error handling, and edge cases not depicted here.

3. WebSocket connections maintain persistent state that is not fully represented in these diagrams. When a response is recorded, all connected presenters viewing that question are notified in real-time.

4. The session toggle functionality uses HTMX to update UI elements without page reloads. The same pattern is used for question toggle functionality.

5. When examining the code, refer to these diagrams to understand where a particular piece of functionality fits into the broader system.
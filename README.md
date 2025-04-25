# ClassPulse

A real-time audience interaction tool for presenters, similar to Mentimeter. ClassPulse allows presenters to create live questions (multiple choice, word clouds, rating scales) and lets audience members join using a unique code to submit answers. Presenters can see real-time visualizations of the results.

## Features

### For Presenters
- Create and manage interactive presentation sessions
- Add different question types:
  - Multiple Choice (visualized as bar charts)
  - Word Clouds
  - Rating Scales (1-10)
- Get a unique session code and QR code for audience to join
- View real-time results and visualizations
- Export results to CSV for further analysis
- Toggle questions active/inactive as needed

### For Audience
- Join sessions with a simple 6-digit code
- View and respond to live questions
- Submit answers anonymously
- See confirmation when responses are recorded

## Tech Stack

- **Backend**: Python with FastHTML framework
- **Frontend**: HTML, CSS, JavaScript
- **Real-time**: WebSockets for live updates
- **Database**: SQLite with FastLite ORM
- **Visualizations**: Chart.js for graphs, jQCloud for word clouds

## Project Structure

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

## Installation

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

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Access the application**
   Open your browser and navigate to http://localhost:5002

## Usage Guide

### For Presenters:

1. **Login**
   - Use the default admin account (username: `admin`, password: `admin123`) to log in

2. **Create a Session**
   - From the dashboard, click "Create New Session"
   - Give your session a name

3. **Add Questions**
   - In the session management page, choose from:
     - New Multiple Choice
     - New Word Cloud
     - New Rating Scale
   - Fill in the question details

4. **Share with Audience**
   - Share the unique 6-digit session code or QR code with your audience
   - Audience members can join at `/join`

5. **Present Mode**
   - Click "Present Mode" to see real-time results as audience members respond

6. **Export Results**
   - Export individual question results or the entire session data to CSV

### For Audience:

1. **Join a Session**
   - Go to the join page (or `/join` URL)
   - Enter the 6-digit session code provided by the presenter

2. **Answer Questions**
   - View active questions and submit your responses
   - For multiple-choice questions, select an option
   - For word clouds, enter words or phrases
   - For rating scales, select a rating from 1-10

## Default Credentials

- **Username:** admin
- **Password:** admin123

## License

[Choose an appropriate license for your project]

## Contributing

[Instructions for contributing to the project]

## Acknowledgements

- FastHTML framework
- Chart.js for visualizations
- jQCloud for word cloud rendering

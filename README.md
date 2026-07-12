# ClassPulse

<!-- BADGES:START -->
[![audience-engagement](https://img.shields.io/badge/-audience--engagement-blue?style=flat-square)](https://github.com/topics/audience-engagement) [![data-visualization](https://img.shields.io/badge/-data--visualization-blue?style=flat-square)](https://github.com/topics/data-visualization) [![flask](https://img.shields.io/badge/-flask-000000?style=flat-square)](https://github.com/topics/flask) [![html](https://img.shields.io/badge/-html-e34f26?style=flat-square)](https://github.com/topics/html) [![interactive-presentation](https://img.shields.io/badge/-interactive--presentation-blue?style=flat-square)](https://github.com/topics/interactive-presentation) [![python](https://img.shields.io/badge/-python-3776ab?style=flat-square)](https://github.com/topics/python) [![qr-code](https://img.shields.io/badge/-qr--code-blue?style=flat-square)](https://github.com/topics/qr-code) [![real-time](https://img.shields.io/badge/-real--time-blue?style=flat-square)](https://github.com/topics/real-time) [![user-management](https://img.shields.io/badge/-user--management-blue?style=flat-square)](https://github.com/topics/user-management) [![edtech](https://img.shields.io/badge/-edtech-4caf50?style=flat-square)](https://github.com/topics/edtech)
<!-- BADGES:END -->

ClassPulse is a real-time audience engagement web application built with Flask. It allows presenters to create interactive sessions with different question types and receive instant feedback from their audience.

## Features

- **Real-time Interaction**: Engage with your audience in real-time using WebSockets
- **Multiple Question Types**: Create multiple-choice questions, word clouds, and rating scales
- **QR Code Generation**: Easy session joining with auto-generated QR codes
- **Results Visualization**: See responses as they come in with instant updates
- **Data Export**: Export results to CSV for further analysis
- **User Management**: Admin panel for user verification and management
- **Session Archive**: Keep your session history organized
- **Cohort Mode**: Let the audience anonymously propose questions and upvote each other's; proposals pass a keyword filter (plus an optional AI check) and flagged ones wait for presenter approval

## Question Types

- **Multiple Choice**: Present options and collect structured responses
- **Word Cloud**: Generate word clouds from free-text responses
- **Rating**: Collect numerical ratings on a defined scale

## Setup

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the application:
   ```
   python app.py
   ```
4. Access the application at http://localhost:5002

## Styling (Tailwind CSS)

The UI is styled with Tailwind, compiled ahead of time to `static/css/tailwind.css`
(this built file is committed, so the app runs without Node). If you change the
markup in `templates/` you need to rebuild the stylesheet:

```
make build-css        # one-off minified build (runs npm install + npm run build:css)
make watch-css        # rebuild automatically while developing
```

Requires Node.js / npm. The Tailwind source lives in `static/src/input.css` and the
content/safelist config in `tailwind.config.js`.

## Admin Access

There is **no default admin account**. On a fresh deployment, the **first person
to register becomes a verified admin automatically** — register, then log in.
Subsequent registrations require admin approval.

The footer of every page shows the build (a link to the exact git commit), so
you can confirm which version/container you are running.

## Requirements

- Python 3.6+
- Flask and extensions (Flask-SQLAlchemy, Flask-SocketIO)
- Additional libraries: qrcode, Pillow

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
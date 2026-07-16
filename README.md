# ClassPulse

<!-- BADGES:START -->
[![audience-engagement](https://img.shields.io/badge/-audience--engagement-blue?style=flat-square)](https://github.com/topics/audience-engagement) [![data-visualization](https://img.shields.io/badge/-data--visualization-blue?style=flat-square)](https://github.com/topics/data-visualization) [![flask](https://img.shields.io/badge/-flask-000000?style=flat-square)](https://github.com/topics/flask) [![html](https://img.shields.io/badge/-html-e34f26?style=flat-square)](https://github.com/topics/html) [![interactive-presentation](https://img.shields.io/badge/-interactive--presentation-blue?style=flat-square)](https://github.com/topics/interactive-presentation) [![python](https://img.shields.io/badge/-python-3776ab?style=flat-square)](https://github.com/topics/python) [![qr-code](https://img.shields.io/badge/-qr--code-blue?style=flat-square)](https://github.com/topics/qr-code) [![real-time](https://img.shields.io/badge/-real--time-blue?style=flat-square)](https://github.com/topics/real-time) [![user-management](https://img.shields.io/badge/-user--management-blue?style=flat-square)](https://github.com/topics/user-management) [![edtech](https://img.shields.io/badge/-edtech-4caf50?style=flat-square)](https://github.com/topics/edtech)
<!-- BADGES:END -->

ClassPulse is a real-time audience engagement web application built with Flask. It allows presenters to create interactive sessions with different question types and receive instant feedback from their audience.

## Features

- **Real-time Interaction**: Engage with your audience in real-time using WebSockets
- **Nine Question Types**: Multiple choice, select-all, ranking, numeric, rating, short answer, word cloud, image choice, and poll-with-other (see below)
- **Image Uploads**: Upload images for image-choice questions — resized and re-encoded server-side to keep storage small — or link to images hosted elsewhere
- **QR Code Generation**: Easy session joining with auto-generated QR codes
- **Results Visualization**: See responses as they come in with instant updates, including live image tallies for image-choice questions
- **AI Question Generation** *(optional)*: Draft and refine questions with an LLM provider you configure
- **Self-service Accounts**: Email-verified registration and password reset via a pluggable email provider (Resend, SMTP, or Gmail); optionally restrict sign-ups to specific email domains
- **Data Export**: Export results to CSV for further analysis
- **User Management**: Admin panel for verifying, archiving, and managing users
- **Session Archive**: Keep your session history organized
- **Cohort Mode**: Let the audience anonymously propose questions and upvote each other's; proposals pass a keyword filter (plus an optional AI check) and flagged ones wait for presenter approval

## Question Types

- **Multiple Choice**: Present options and collect structured responses
- **Select All**: Multiple-answer version of multiple choice
- **Ranking**: Ask the audience to order a set of items
- **Numeric**: Collect numbers, with an optional min/max range
- **Rating**: Collect numerical ratings on a defined scale
- **Short Answer**: Free-text responses, viewable as a list or a word cloud
- **Word Cloud**: Generate word clouds from free-text responses
- **Image Choice**: Compare images (uploaded or linked) and vote — results show the images with live tallies
- **Poll w/ Other**: Multiple choice plus a free-text "Other" option

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

## Accounts & Admin Access

There is **no default admin account**. On a fresh deployment, the **first person
to register becomes a verified admin automatically** — register, then log in.

Everyone who registers after that **verifies their email with a code** before
they can log in. Configure an email provider (Resend, SMTP, or Gmail) in `.env`
to send those codes — see [`.env.example`](.env.example); the default `dev`
provider just logs codes to the console for local testing. Admins can also
verify, archive, and manage users from the admin panel, and sign-ups can be
restricted to specific email domains (`ALLOWED_DOMAINS`).

Forgotten passwords are recovered with an emailed reset code. If you are ever
locked out with no email configured, an operator can reset any account directly
on the server with `scripts/reset-password.sh`.

The footer of every page shows the build (a link to the exact git commit), so
you can confirm which version/container you are running.

## Configuration & Deployment

Configuration is environment-driven — copy [`.env.example`](.env.example) to
`.env` and fill in what you need (secret key, email provider, optional AI
provider, image-upload limits, domain restrictions). For production deployment
(Docker/systemd, reverse proxy, persistence) see [DEPLOYMENT.md](DEPLOYMENT.md),
and for the security model and required settings see [SECURITY.md](SECURITY.md).

## Requirements

- Python 3.9+
- Flask and extensions (Flask-SQLAlchemy, Flask-SocketIO, Flask-WTF, Flask-Limiter)
- Additional libraries: qrcode, Pillow, requests

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
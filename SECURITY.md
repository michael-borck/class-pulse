# Security

ClassPulse is a lightweight, self-hosted audience-engagement tool intended for
formative classroom use (not high-stakes assessment). This document records the
security model, required configuration, and known residual risks.

## Required configuration

Copy `.env.example` to `.env` and set at least:

| Variable | Why it matters |
| --- | --- |
| `SECRET_KEY` | Signs session cookies. A known/shared value lets anyone forge an admin session. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SESSION_COOKIE_SECURE` | Set to `true` when serving over HTTPS so cookies are not sent over plain HTTP (also enables HSTS). |
| `TRUST_PROXY` | Set to `1` when behind a reverse proxy (Caddy/nginx) so rate limits key on the real client IP and generated join URLs use https. |

`docker compose` will refuse to start unless `SECRET_KEY` is set.

## What is protected

- **Session forgery** — `SECRET_KEY` is required from the environment; no known fallback ships. Presenter sessions expire after `PERMANENT_SESSION_LIFETIME` (default 24 h).
- **Default credentials** — none; no admin account is auto-created. The first registrant becomes the verified admin (guarded against concurrent-registration races).
- **Debug RCE** — the Werkzeug debugger is off unless `FLASK_ENV=development`/`DEBUG=true`.
- **CSRF** — all state-changing form and AJAX requests require a CSRF token (Flask-WTF).
- **Brute force / abuse** — rate limits on `/login` (10/min), `/register` (20/h), `/join` (30/min), `/audience/respond` (60/min), and the AI endpoint (10/min). Minimum password length is 10. Login timing does not reveal whether a username exists.
- **Passwords** — PBKDF2-HMAC-SHA256 with 600k iterations (werkzeug); legacy 100k-iteration hashes are verified and transparently upgraded on the next login.
- **Input validation** — audience responses are validated against the question definition (choice answers must be one of the options; ratings/numerics bounds-checked; free text length-capped). Request bodies are capped at `MAX_CONTENT_LENGTH` (256 KB default). The anonymous respondent cookie must be a well-formed UUID.
- **Live-result snooping** — Socket.IO room joins are authorized: results stream only for publicly live questions, or to the authenticated session owner. IDs cannot be enumerated to watch other sessions.
- **CSV formula injection** — exported response values are prefix-escaped so `=`/`+`/`-`/`@` cells don't execute in Excel/Sheets.
- **Headers** — `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy` on every response; `Strict-Transport-Security` when `SESSION_COOKIE_SECURE=true`.
- **Cookies** — `HttpOnly`, `SameSite=Lax`, and `Secure` (opt-in) on session and respondent cookies.
- **Supply chain** — all front-end libraries (Socket.IO client, Chart.js, jQuery, jqCloud) are vendored into `static/vendor/`; no third-party CDN can inject script. Google Fonts is the only external origin (styles/fonts, allowed by the CSP).
- **Container** — the Docker image runs as a non-root user (UID 1000) and contains no compiler toolchain.
- **Info disclosure** — exception details are logged server-side, not shown to users. All DB access is via the SQLAlchemy ORM (no raw SQL).

## Deployment notes

- Run behind an HTTPS reverse proxy; set `SESSION_COOKIE_SECURE=true` and `TRUST_PROXY=1` (the provided `docker-compose.deploy.yml` does both).
- Run **one** gunicorn worker (the provided Dockerfile/start.sh do). Socket.IO
  long-polling is stateful and broadcasts don't cross worker processes; to
  scale out, set `SOCKETIO_MESSAGE_QUEUE` (Redis) and a shared
  `RATELIMIT_STORAGE_URI`, and enable sticky sessions at the proxy.
- AI question generation is optional and global (one provider in `.env`):
  `AI_PROVIDER` (`openai`|`anthropic`), `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`.
  The API key is a plaintext secret in `.env` (0600, gitignored) — protect it like
  `SECRET_KEY`. Leave `AI_PROVIDER` blank to disable generation.

## Known residual risks

- **Audience identity is not authenticated.** The respondent ID is a client-side
  cookie, so a participant can clear it to submit again. This is acceptable for
  formative polling but means response counts are **not** a trustworthy tally for
  anything graded.
- **The CSP allows inline scripts** (`'unsafe-inline'`), because page scripts are
  currently inline. It still restricts sources for scripts, connections, and
  objects. Moving to nonce-based CSP would require externalising page scripts.
- **Image-choice questions load presenter-supplied image URLs** (`img-src https:`).
  Presenters are trusted users, but a malicious presenter could point images at a
  tracking endpoint.

## Reporting

Report security issues privately to the maintainer rather than via public issues.

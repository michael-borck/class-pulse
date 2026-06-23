# Security

ClassPulse is a lightweight, self-hosted audience-engagement tool intended for
formative classroom use (not high-stakes assessment). This document records the
security model, required configuration, and known residual risks.

## Required configuration

Copy `.env.example` to `.env` and set at least:

| Variable | Why it matters |
| --- | --- |
| `SECRET_KEY` | Signs session cookies. A known/shared value lets anyone forge an admin session. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ENCRYPTION_KEY` | Encrypts stored cloud API keys at rest. Must be stable, or stored keys become undecryptable after a restart. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DEFAULT_ADMIN_PASS` | Optional. If left blank, a strong random admin password is generated and printed **once** on first run. There is no hardcoded default. |
| `SESSION_COOKIE_SECURE` | Set to `true` when serving over HTTPS so cookies are not sent over plain HTTP. |

`docker compose` will refuse to start unless `SECRET_KEY` is set.

## What is protected

- **Session forgery** — `SECRET_KEY` is required from the environment; no known fallback ships.
- **Default credentials** — no hardcoded admin password; random generated on first run.
- **Debug RCE** — the Werkzeug debugger is off unless `FLASK_ENV=development`/`DEBUG=true`.
- **CSRF** — all state-changing form and AJAX requests require a CSRF token (Flask-WTF).
- **SSRF** — user-supplied AI provider URLs are validated; link-local/metadata
  addresses (e.g. `169.254.169.254`) are blocked. Loopback/private are allowed so
  local Ollama still works.
- **Brute force** — `/login` is rate-limited (10/min). Minimum password length is 10.
- **Cookies** — `HttpOnly`, `SameSite=Lax`, and `Secure` (opt-in) on session and respondent cookies.
- **Info disclosure** — exception details are logged server-side, not shown to users.
- **Transport** — passwords use PBKDF2-HMAC-SHA256 (100k iterations, per-user salt); all DB access is via the SQLAlchemy ORM (no raw SQL).

## Deployment notes

- Run behind an HTTPS reverse proxy and set `SESSION_COOKIE_SECURE=true`.
- The bundled `start.sh`/Docker use gunicorn with the `wsgi:application` entrypoint,
  which initializes the schema and bootstrap admin. With sync/gthread workers,
  Socket.IO uses HTTP long-polling; for true websockets use an eventlet/gevent worker.
- For multi-worker gunicorn, set a shared `RATELIMIT_STORAGE_URI` (e.g. Redis);
  the default in-memory limiter is per-process.

## Known residual risks

- **Audience identity is not authenticated.** The respondent ID is a client-side
  cookie, so a participant can clear it to submit again. This is acceptable for
  formative polling but means response counts are **not** a trustworthy tally for
  anything graded.
- **Front-end libraries load from CDNs without Subresource Integrity (SRI).** A CDN
  compromise could inject script. For hardened or offline/campus deployments,
  vendor the JS/CSS locally (jQuery, Chart.js, jqcloud, Socket.IO client) or add SRI
  hashes. Versions are pinned.
- **SSRF guard allows private ranges.** A verified user could point an AI URL at an
  internal host on the same network. Mitigated by the admin-verification gate; only
  grant verification to trusted presenters.

## Reporting

Report security issues privately to the maintainer rather than via public issues.

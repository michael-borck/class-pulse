"""Email delivery: a swappable provider abstraction plus the ClassPulse messages.

Configuration is environment-driven (12-factor); see .env.example. The provider
is chosen by EMAIL_PROVIDER and defaults to 'dev', which prints the message to
the log instead of sending it — so the app runs with zero email config and the
verification/reset codes are still readable during local development.

Ported (and Flask-adapted) from the sibling the-ai-exchange project.
"""

import logging
import os
import smtplib
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

import requests

logger = logging.getLogger(__name__)


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes")


def _mail_from() -> tuple[str, str]:
    """(from_email, from_name), with sensible fallbacks."""
    return (
        _env("MAIL_FROM", "no-reply@classpulse.local"),
        _env("MAIL_FROM_NAME", "ClassPulse"),
    )


class EmailProvider(ABC):
    """Send an email with both HTML and plain-text bodies. Returns success."""

    @abstractmethod
    def send_email(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        ...


class DevEmailProvider(EmailProvider):
    """Logs the message instead of sending — the default, needs no config."""

    def send_email(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        from_email, from_name = _mail_from()
        # Use the module logger at INFO so codes are visible in `docker logs`
        # during local/dev runs without emitting to real recipients.
        logger.info(
            "\n%s\n[DEV EMAIL] (EMAIL_PROVIDER=dev — not actually sent)\n%s\n"
            "From: %s\nTo: %s\nSubject: %s\n%s\n%s\n%s",
            "=" * 70, "=" * 70,
            formataddr((from_name, from_email)), to_email, subject,
            "=" * 70, text_body, "=" * 70,
        )
        return True


class SMTPEmailProvider(EmailProvider):
    """Generic SMTP for a custom mail server (EMAIL_PROVIDER=smtp)."""

    def send_email(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        from_email, from_name = _mail_from()
        server = _env("SMTP_SERVER")
        port = int(_env("SMTP_PORT", "587") or 587)
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = formataddr((from_name, from_email))
            msg["To"] = to_email
            # Plain text first, HTML last (clients prefer the last part).
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            smtp: smtplib.SMTP
            if _env_bool("SMTP_USE_SSL"):
                smtp = smtplib.SMTP_SSL(server, port)
            else:
                smtp = smtplib.SMTP(server, port)
            with smtp:
                if _env_bool("SMTP_USE_TLS", default=True) and not _env_bool("SMTP_USE_SSL"):
                    smtp.starttls()
                user, password = _env("SMTP_USER"), _env("SMTP_PASSWORD")
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(msg)
            logger.info("SMTP: sent '%s' to %s", subject, to_email)
            return True
        except Exception as e:
            logger.error("SMTP: failed to send '%s' to %s: %s", subject, to_email, e)
            return False


class GmailEmailProvider(EmailProvider):
    """Gmail via an app-specific password (EMAIL_PROVIDER=gmail)."""

    def send_email(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        from_email, from_name = _mail_from()
        app_password = _env("GMAIL_APP_PASSWORD")
        if not app_password:
            logger.error("Gmail: GMAIL_APP_PASSWORD not configured")
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = formataddr((from_name, from_email))
            msg["To"] = to_email
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(from_email, app_password)
                smtp.send_message(msg)
            logger.info("Gmail: sent '%s' to %s", subject, to_email)
            return True
        except Exception as e:
            logger.error("Gmail: failed to send '%s' to %s: %s", subject, to_email, e)
            return False


class ResendEmailProvider(EmailProvider):
    """Resend transactional email API — https://resend.com (EMAIL_PROVIDER=resend)."""

    def send_email(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        from_email, from_name = _mail_from()
        api_key = _env("RESEND_API_KEY")
        if not api_key:
            logger.error("Resend: RESEND_API_KEY not configured")
            return False
        try:
            response = requests.post(
                "https://api.resend.com/emails",
                json={
                    "from": formataddr((from_name, from_email)),
                    "to": [to_email],
                    "subject": subject,
                    "html": html_body,
                    "text": text_body,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            if response.status_code in (200, 202):
                logger.info("Resend: sent '%s' to %s", subject, to_email)
                return True
            logger.error(
                "Resend: failed to send '%s' to %s: %s %s",
                subject, to_email, response.status_code, response.text,
            )
            return False
        except Exception as e:
            logger.error("Resend: failed to send '%s' to %s: %s", subject, to_email, e)
            return False


_PROVIDERS = {
    "dev": DevEmailProvider,
    "smtp": SMTPEmailProvider,
    "custom": SMTPEmailProvider,  # alias
    "gmail": GmailEmailProvider,
    "resend": ResendEmailProvider,
}


def get_email_provider() -> EmailProvider:
    """Return the configured provider (defaults to 'dev')."""
    name = _env("EMAIL_PROVIDER", "dev").lower() or "dev"
    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        logger.error(
            "Unknown EMAIL_PROVIDER=%r; falling back to 'dev'. Supported: %s",
            name, ", ".join(sorted(_PROVIDERS)),
        )
        provider_cls = DevEmailProvider
    return provider_cls()


def send_email(to_email: str, subject: str, html_body: str, text_body: str) -> bool:
    """Send via the configured provider. Never raises; returns success."""
    try:
        return get_email_provider().send_email(to_email, subject, html_body, text_body)
    except Exception as e:  # defensive: a broken provider must not 500 a request
        logger.error("Email send failed for '%s' to %s: %s", subject, to_email, e)
        return False


# --- ClassPulse messages ---------------------------------------------------
# Codes are shown verbatim (recipient types them back). The optional link is a
# convenience that pre-fills the code on the verify/reset page.

def _wrap_html(heading: str, intro: str, code: str, footer: str) -> str:
    return f"""\
<div style="font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:480px;margin:0 auto;">
  <h2 style="color:#4f46e5;">{heading}</h2>
  <p>{intro}</p>
  <p style="font-size:28px;font-weight:700;letter-spacing:4px;background:#f3f4f6;
            padding:16px 24px;border-radius:8px;text-align:center;margin:24px 0;">{code}</p>
  <p style="color:#6b7280;font-size:13px;">{footer}</p>
</div>"""


def send_verification_email(to_email: str, display_name: str, code: str,
                            ttl_minutes: int) -> bool:
    subject = "Verify your ClassPulse account"
    intro = (f"Hi {display_name}, welcome to ClassPulse. Enter this code on the "
             f"verification page to activate your account:")
    footer = f"This code expires in {ttl_minutes} minutes. If you didn't register, ignore this email."
    text = (f"Hi {display_name},\n\nWelcome to ClassPulse. Your verification code is:\n\n"
            f"    {code}\n\nEnter it on the verification page to activate your account. "
            f"It expires in {ttl_minutes} minutes.\n\nIf you didn't register, ignore this email.\n")
    html = _wrap_html("Verify your account", intro, code, footer)
    return send_email(to_email, subject, html, text)


def send_password_reset_email(to_email: str, display_name: str, code: str,
                              ttl_minutes: int) -> bool:
    subject = "Reset your ClassPulse password"
    intro = (f"Hi {display_name}, we received a request to reset your ClassPulse "
             f"password. Enter this code on the reset page:")
    footer = (f"This code expires in {ttl_minutes} minutes. If you didn't request a "
              f"reset, ignore this email — your password stays unchanged.")
    text = (f"Hi {display_name},\n\nWe received a request to reset your ClassPulse password. "
            f"Your reset code is:\n\n    {code}\n\nEnter it on the reset page. It expires in "
            f"{ttl_minutes} minutes.\n\nIf you didn't request a reset, ignore this email.\n")
    html = _wrap_html("Reset your password", intro, code, footer)
    return send_email(to_email, subject, html, text)

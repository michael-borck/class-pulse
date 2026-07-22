"""Small helpers: QR codes, session codes, CSV safety, Jinja filters."""

import base64
import io
import json
import secrets
from datetime import datetime
from typing import Optional

import qrcode as qr_code_lib
from flask import current_app
from PIL import Image
from sqlalchemy import func

from .models import Session


def create_qr_code_data(url: str, size: int = 200) -> Optional[str]:
    """Creates a QR code data URL for a given URL."""
    try:
        qr = qr_code_lib.QRCode(
            version=1,
            error_correction=qr_code_lib.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        # NEAREST keeps module edges hard — a smoothed QR blurs at projector size
        # and scanners struggle with it.
        img = qr.make_image(fill_color="black", back_color="white") \
            .resize((size, size), Image.NEAREST)
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{img_str}"
    except Exception:
        current_app.logger.exception("Error generating QR code")
        return None


# Crockford-style alphabet: I, L and O are omitted so no character can be
# mistaken for 1 or 0, and U is omitted so a code can't spell something
# unfortunate. Codes get read off a projector and typed by a room full of
# people, so one ambiguous glyph costs real class time.
SESSION_CODE_ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'

# Applied to typed codes, and to stored codes when matching. Lets someone who
# types O for 0 in anyway, and keeps codes issued before the alphabet was
# narrowed (which really can contain O/I/L) working.
_CODE_CONFUSABLES = {'O': '0', 'I': '1', 'L': '1'}


def normalize_session_code(raw) -> str:
    """Upper-case a typed session code and fold confusable glyphs onto the
    canonical alphabet."""
    return ''.join(_CODE_CONFUSABLES.get(ch, ch)
                   for ch in (raw or '').strip().upper())


def session_code_match(code: str):
    """A filter expression matching `code` against Session.code with the same
    folding applied to both sides, so O/0 and I/L/1 confusion can't miss."""
    col = Session.code
    for src, dst in _CODE_CONFUSABLES.items():
        col = func.replace(col, src, dst)
    return col == normalize_session_code(code)


def generate_session_code(length: int = 6) -> str:
    """Generates a random unambiguous code, ensuring uniqueness."""
    while True:
        code = ''.join(secrets.choice(SESSION_CODE_ALPHABET) for _ in range(length))
        # Compared folded, so a new code can't collide with an older one that
        # differs from it only by O/0 or I/L/1.
        if not Session.query.filter(session_code_match(code)).first():
            return code


def csv_safe(value) -> str:
    """Neutralise spreadsheet formula injection in CSV exports.

    Cell values beginning with =, +, -, @ (or tab/CR) execute as formulas when
    the CSV is opened in Excel/Sheets. Audience responses are attacker-
    controlled, so prefix such values with a quote (OWASP recommendation).
    """
    s = str(value)
    if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + s
    return s


def format_datetime_filter(value, format='%Y-%m-%d %H:%M'):
    """Formats an ISO datetime string."""
    if value is None:
        return ""
    try:
        dt_object = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt_object.strftime(format)
    except (ValueError, TypeError):
        return value  # Return original if parsing fails


def fromjson_filter(value):
    """Loads JSON string into Python object."""
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        if isinstance(value, str):
            if value.strip().startswith('['):
                return []
            if value.strip().startswith('{'):
                return {}
        return {}  # Default fallback

"""Small helpers: QR codes, session codes, CSV safety, Jinja filters."""

import base64
import io
import json
import secrets
from datetime import datetime
from typing import Optional

import qrcode as qr_code_lib
from flask import current_app

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
        img = qr.make_image(fill_color="black", back_color="white").resize((size, size))
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{img_str}"
    except Exception:
        current_app.logger.exception("Error generating QR code")
        return None


def generate_session_code(length: int = 6) -> str:
    """Generates a random alphanumeric code, ensuring uniqueness."""
    while True:
        code = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
                       for _ in range(length))
        if not Session.query.filter_by(code=code).first():
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

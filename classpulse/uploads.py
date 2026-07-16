"""Presenter image uploads for image_choice questions.

Uploads are validated, stripped of metadata, downscaled, and re-encoded to JPEG
before being stored under the *persisted* instance/uploads/<session_id>/
directory — NOT static/, which is baked into the Docker image and wiped on every
`docker compose pull`. Re-encoding is the core safety measure: Pillow rejects
anything it can't decode as a raster, and the JPEG output normalises the file,
defeating SVG/script/polyglot payloads. The client filename is never trusted;
the server assigns a random UUID name.

Uploaded images become ordinary "/uploads/<sid>/<name>" URLs that flow through
the existing image_choice option pipeline (questions.py) unchanged — same-origin,
allowed by the CSP `img-src 'self'`.
"""

import io
import os
import re
import shutil
import uuid

from flask import abort, current_app, jsonify, request, send_from_directory, session
from PIL import Image, ImageOps, UnidentifiedImageError

from .auth import login_required
from .extensions import limiter
from .models import Session

# Server-assigned names only: 32 hex chars (uuid4) + .jpg. Anything else can't
# have been produced by us, so the serve route rejects it (defence in depth on
# top of send_from_directory's own traversal safety).
_FILENAME_RE = re.compile(r'^[0-9a-f]{32}\.jpg$')


def _session_dir(session_id):
    return os.path.join(current_app.config['UPLOAD_DIR'], str(int(session_id)))


def process_and_save(file_storage, session_id):
    """Validate/resize/re-encode an uploaded image and return its served URL.

    Raises ValueError with a user-safe message on any rejection.
    """
    if file_storage is None or not file_storage.filename:
        raise ValueError("No image was uploaded.")

    max_bytes = current_app.config['UPLOAD_MAX_BYTES']
    # Read into memory (already bounded by MAX_CONTENT_LENGTH) and measure the
    # real size rather than trusting the Content-Length header.
    data = file_storage.read(max_bytes + 1)
    if not data:
        raise ValueError("The uploaded file is empty.")
    if len(data) > max_bytes:
        raise ValueError(f"Image is too large (max {max_bytes // (1024 * 1024)} MB).")

    try:
        # verify() does a light integrity check but consumes the file object,
        # so reopen from a fresh stream for the actual decode.
        Image.open(io.BytesIO(data)).verify()
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)          # honour orientation
        img = img.convert("RGB")                     # flatten alpha, drop palette/metadata
        img.thumbnail((current_app.config['IMAGE_MAX_DIM'],
                       current_app.config['IMAGE_MAX_DIM']))  # downscale, keep aspect
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ValueError("That file isn't a valid image.") from None

    session_dir = _session_dir(session_id)
    os.makedirs(session_dir, exist_ok=True)
    name = uuid.uuid4().hex + ".jpg"
    img.save(os.path.join(session_dir, name), "JPEG", quality=82, optimize=True)
    return f"/uploads/{int(session_id)}/{name}"


def delete_session_uploads(session_id):
    """Remove a session's upload directory, if any (best-effort)."""
    shutil.rmtree(_session_dir(session_id), ignore_errors=True)


def init_app(app):
    # Reject decompression bombs: a small file that decodes to a huge bitmap.
    # Pillow raises DecompressionBombError past this pixel count during decode,
    # which process_and_save() catches and turns into a clean rejection.
    Image.MAX_IMAGE_PIXELS = app.config['IMAGE_MAX_PIXELS']

    @app.route('/api/sessions/<int:session_id>/upload-image', methods=['POST'])
    @limiter.limit("60 per hour")
    @login_required
    def api_upload_image(session_id):
        # Only the session's own presenter may upload to it.
        owned = Session.query.filter_by(id=session_id, user_id=session['user_id']).first()
        if owned is None:
            abort(404)
        try:
            url = process_and_save(request.files.get('image'), session_id)
        except ValueError as e:
            return jsonify({"success": False, "message": str(e)}), 400
        return jsonify({"success": True, "url": url})

    @app.route('/uploads/<int:session_id>/<filename>')
    @limiter.exempt
    def serve_upload(session_id, filename):
        # Public by design: the anonymous audience must load these images. Names
        # are unguessable UUIDs; the strict pattern plus send_from_directory
        # block any path traversal.
        if not _FILENAME_RE.match(filename):
            abort(404)
        return send_from_directory(_session_dir(session_id), filename, max_age=86400)

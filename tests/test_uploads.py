"""Image upload processing, serving, access control, and cleanup."""

import io
import os

import pytest
from PIL import Image

from classpulse.extensions import db

from conftest import (
    add_response, create_question, create_session, create_user, login, make_app,
)


def png_bytes(size=(12, 12), color=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, 'PNG')
    return buf.getvalue()


@pytest.fixture()
def app(tmp_path):
    # Redirect uploads to a temp dir so tests never touch the repo's instance/.
    application = make_app({'UPLOAD_DIR': str(tmp_path / 'uploads')})
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def upload(client, session_id, data=None, filename='pic.png', field='image'):
    payload = png_bytes() if data is None else data
    return client.post(
        f'/api/sessions/{session_id}/upload-image',
        data={field: (io.BytesIO(payload), filename)},
        content_type='multipart/form-data',
    )


def _upload_path(app, url):
    """Map a /uploads/<sid>/<name> URL to its on-disk path."""
    _, _, sid, name = url.split('/')
    return os.path.join(app.config['UPLOAD_DIR'], sid, name)


def test_valid_upload_returns_url_and_serves(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    login(client, 'alice')

    resp = upload(client, sid)
    assert resp.status_code == 200
    url = resp.get_json()['url']
    assert url.startswith(f'/uploads/{sid}/') and url.endswith('.jpg')
    # The re-encoded file exists on disk...
    assert os.path.exists(_upload_path(app, url))
    # ...and is served as a JPEG.
    served = client.get(url)
    assert served.status_code == 200
    assert served.mimetype == 'image/jpeg'


def test_reencoded_output_is_downscaled(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    login(client, 'alice')
    # Upload something larger than IMAGE_MAX_DIM and confirm it's shrunk.
    big = png_bytes(size=(3000, 2000))
    url = upload(client, sid, data=big).get_json()['url']
    with Image.open(_upload_path(app, url)) as out:
        assert max(out.size) <= app.config['IMAGE_MAX_DIM']


def test_non_image_rejected(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    login(client, 'alice')
    resp = upload(client, sid, data=b'this is definitely not an image')
    assert resp.status_code == 400
    assert 'valid image' in resp.get_json()['message']


def test_disguised_text_file_rejected(app, client):
    # A .jpg extension doesn't fool the decoder.
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    login(client, 'alice')
    resp = upload(client, sid, data=b'<svg onload=alert(1)>', filename='evil.jpg')
    assert resp.status_code == 400


def test_oversized_rejected():
    app = make_app({'UPLOAD_MAX_BYTES': 50})
    try:
        client = app.test_client()
        uid = create_user(app, 'alice')
        sid = create_session(app, uid)
        login(client, 'alice')
        resp = upload(client, sid)  # a normal PNG is well over 50 bytes
        assert resp.status_code == 400
        assert 'too large' in resp.get_json()['message']
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_serve_rejects_bad_filenames(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    login(client, 'alice')
    # Not a server-issued UUID name -> 404, never a filesystem lookup.
    assert client.get(f'/uploads/{sid}/notauuid.jpg').status_code == 404
    assert client.get(f'/uploads/{sid}/config.txt').status_code == 404
    # Well-formed but nonexistent -> 404.
    assert client.get(f'/uploads/{sid}/{"a"*32}.jpg').status_code == 404


def test_upload_requires_ownership(app, client):
    alice = create_user(app, 'alice')
    create_user(app, 'bob')
    sid = create_session(app, alice)  # alice's session
    login(client, 'bob')
    assert upload(client, sid).status_code == 404


def test_upload_requires_login(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    resp = upload(client, sid)  # not logged in
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_hard_delete_removes_uploads(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    login(client, 'alice')
    url = upload(client, sid).get_json()['url']
    path = _upload_path(app, url)
    assert os.path.exists(path)

    resp = client.post(f'/api/sessions/{sid}/delete')
    assert resp.get_json()['deleted'] == 'hard'
    assert not os.path.exists(path)


def test_soft_delete_keeps_uploads(app, client):
    uid = create_user(app, 'alice')
    sid = create_session(app, uid)
    login(client, 'alice')
    url = upload(client, sid).get_json()['url']
    path = _upload_path(app, url)

    # A response forces a soft delete, which must preserve the images.
    qid = create_question(app, sid)
    add_response(app, qid, sid, 'Red', 'respondent-1')

    resp = client.post(f'/api/sessions/{sid}/delete')
    assert resp.get_json()['deleted'] == 'soft'
    assert os.path.exists(path)

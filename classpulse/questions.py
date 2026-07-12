"""Question option parsing/validation and serialization shared by routes."""

import json

from .models import Response

VALID_QUESTION_TYPES = (
    'multiple_choice', 'word_cloud', 'rating',
    'multi_select', 'short_answer', 'ranking', 'numeric',
    'image_choice', 'multiple_choice_other',
)

# Server-side caps for content authored by presenters (titles/options) and,
# more importantly, submitted by the anonymous audience (see audience.py).
MAX_TITLE_LEN = 255
MAX_OPTION_LEN = 500
MAX_OPTIONS = 50


def build_options(q_type, src):
    """Build the options JSON value for a question from a dict-like source.

    `src` exposes 'options' (newline-string or list), 'max_rating', and
    'min'/'max'/'step'. Returns (options_value, error_or_None).
    """
    if q_type in ('multiple_choice', 'multi_select', 'ranking', 'multiple_choice_other'):
        opts = src.get('options') or []
        if isinstance(opts, str):
            opts = opts.splitlines()
        opts = [str(o).strip()[:MAX_OPTION_LEN] for o in opts if str(o).strip()]
        if len(opts) < 2:
            return (None, 'Add at least two options.')
        if len(opts) > MAX_OPTIONS:
            return (None, f'Too many options (max {MAX_OPTIONS}).')
        return (opts, None)
    if q_type == 'image_choice':
        raw = src.get('options') or []
        if isinstance(raw, str):
            raw = raw.splitlines()
        items = []
        for i, line in enumerate([str(line).strip() for line in raw if str(line).strip()], 1):
            if '|' in line:
                label, url = line.split('|', 1)
                items.append({'label': label.strip()[:MAX_OPTION_LEN], 'url': url.strip()})
            else:
                seg = line.rstrip('/').split('/')[-1].split('?')[0]
                label = seg.rsplit('.', 1)[0] if '.' in seg else seg
                items.append({'label': (label or f'Image {i}')[:MAX_OPTION_LEN], 'url': line})
        if len(items) < 2:
            return (None, 'Add at least two images (one label|url per line).')
        if len(items) > MAX_OPTIONS:
            return (None, f'Too many images (max {MAX_OPTIONS}).')
        return (items, None)
    if q_type == 'numeric':
        cfg = {}
        for k in ('min', 'max', 'step'):
            v = src.get(k)
            if v not in (None, ''):
                try:
                    cfg[k] = float(v)
                except (ValueError, TypeError):
                    pass
        return (cfg, None)
    if q_type == 'rating':
        try:
            mx = int(src.get('max_rating', 5))
        except (ValueError, TypeError):
            mx = 5
        return ({'max_rating': max(2, min(10, mx))}, None)
    # word_cloud, short_answer carry no config
    return ({}, None)


def parse_question_payload(data):
    """Validate/normalise an add/edit question payload.

    Returns (error_message_or_None, q_type, title, options_value)."""
    q_type = data.get('type')
    if q_type not in VALID_QUESTION_TYPES:
        return ('Invalid question type.', None, None, None)
    title = (data.get('title') or '').strip()
    if not title:
        return ('Question title is required.', None, None, None)
    if len(title) > MAX_TITLE_LEN:
        return (f'Question title is too long (max {MAX_TITLE_LEN} characters).', None, None, None)
    options_value, err = build_options(q_type, data)
    if err:
        return (err, None, None, None)
    return (None, q_type, title, options_value)


def parsed_options(question):
    """The question's options JSON parsed, or a sensible empty value."""
    try:
        return json.loads(question.options) if question.options else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def question_to_dict(q):
    """Serialize a Question for the builder UI."""
    parsed = parsed_options(q)
    data = {
        'id': q.id,
        'type': q.type,
        'title': q.title,
        'active': q.active,
        'response_count': Response.query.filter_by(question_id=q.id).count(),
        'options': parsed if (q.type in ('multiple_choice', 'multi_select', 'ranking',
                                         'multiple_choice_other', 'image_choice')
                              and isinstance(parsed, list)) else [],
        'max_rating': 5,
    }
    if q.type == 'rating' and isinstance(parsed, dict):
        try:
            data['max_rating'] = int(parsed.get('max_rating', 5))
        except (ValueError, TypeError):
            data['max_rating'] = 5
    if q.type == 'numeric' and isinstance(parsed, dict):
        data['numeric'] = {k: parsed[k] for k in ('min', 'max', 'step') if k in parsed}
    return data


def session_to_dict(s, include_questions=False):
    d = {
        'id': s.id, 'name': s.name, 'code': s.code,
        'active': s.active, 'archived': s.archived,
        'allow_proposals': s.allow_proposals,
        'question_count': len(s.questions),
    }
    if include_questions:
        d['questions'] = [question_to_dict(q) for q in s.questions]
    return d

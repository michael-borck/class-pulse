"""Question option parsing/validation and serialization shared by routes."""

import json
import math

from .models import Response

VALID_QUESTION_TYPES = (
    'multiple_choice', 'word_cloud', 'rating',
    'multi_select', 'short_answer', 'ranking', 'numeric',
    'image_choice', 'multiple_choice_other',
    'emoji', 'matrix', 'scatter',
)

# Server-side caps for content authored by presenters (titles/options) and,
# more importantly, submitted by the anonymous audience (see audience.py).
MAX_TITLE_LEN = 255
MAX_OPTION_LEN = 500
MAX_OPTIONS = 50

# Emoji polls: the audience picks one glyph from a presenter-chosen list.
# Compound emoji (ZWJ sequences, skin-tone modifiers) can be several code
# points long, so the per-emoji cap is generous but small.
MAX_EMOJI_OPTIONS = 12
MAX_EMOJI_LEN = 16

# Matrix polls: audience taps one cell of a cols×rows labelled grid. 2×2 is the
# classic quadrant; up to 4×4 stays tappable on a phone.
MATRIX_MIN_DIM = 2
MATRIX_MAX_DIM = 4
MAX_AXIS_LABEL_LEN = 60

# Scatter polls: audience drops a point on a 0–100 × 0–100 plane; the optional
# colour dimension is chosen from this fixed palette. Keys are what the
# audience picks and what gets stored; values are display hexes for the UI.
SCATTER_COLORS = {
    'red': '#ef4444', 'orange': '#f97316', 'amber': '#f59e0b', 'green': '#22c55e',
    'teal': '#14b8a6', 'blue': '#3b82f6', 'purple': '#8b5cf6', 'pink': '#ec4899',
}
SCATTER_SIZES = ('sm', 'md', 'lg')


def _option_lines(raw, split=str.splitlines):
    """Options arrive as one string (split it) or a list; anything else
    (a number, an object from a malformed JSON body) counts as none."""
    if isinstance(raw, str):
        return split(raw)
    return list(raw) if isinstance(raw, (list, tuple)) else []


def build_options(q_type, src):
    """Build the options JSON value for a question from a dict-like source.

    `src` exposes 'options' (newline-string or list), 'max_rating', and
    'min'/'max'/'step'. Returns (options_value, error_or_None).
    """
    if q_type in ('multiple_choice', 'multi_select', 'ranking', 'multiple_choice_other'):
        opts = _option_lines(src.get('options'))
        opts = [str(o).strip()[:MAX_OPTION_LEN] for o in opts if str(o).strip()]
        # Duplicates make a ranking question unanswerable (two options would
        # share one rank slot) and split votes elsewhere, so drop repeats.
        opts = list(dict.fromkeys(opts))
        if len(opts) < 2:
            return (None, 'Add at least two options.')
        if len(opts) > MAX_OPTIONS:
            return (None, f'Too many options (max {MAX_OPTIONS}).')
        return (opts, None)
    if q_type == 'image_choice':
        raw = _option_lines(src.get('options'))
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
                    f = float(v)
                except (ValueError, TypeError):
                    continue
                if math.isfinite(f):  # "nan"/"inf" parse but aren't usable bounds
                    cfg[k] = f
        if 'min' in cfg and 'max' in cfg and cfg['min'] > cfg['max']:
            return (None, 'The minimum must not be greater than the maximum.')
        return (cfg, None)
    if q_type == 'rating':
        try:
            mx = int(src.get('max_rating', 5))
        except (ValueError, TypeError):
            mx = 5
        return ({'max_rating': max(2, min(10, mx))}, None)
    if q_type == 'emoji':
        # Split on any whitespace: presenters paste emojis space-separated.
        raw = _option_lines(src.get('options'), split=str.split)
        emojis = []
        for e in raw:
            e = str(e).strip()[:MAX_EMOJI_LEN]
            if e and e not in emojis:
                emojis.append(e)
        if len(emojis) < 2:
            return (None, 'Add at least two emojis.')
        if len(emojis) > MAX_EMOJI_OPTIONS:
            return (None, f'Too many emojis (max {MAX_EMOJI_OPTIONS}).')
        return (emojis, None)
    if q_type == 'matrix':
        def _dim(key):
            try:
                return max(MATRIX_MIN_DIM, min(MATRIX_MAX_DIM, int(src.get(key))))
            except (ValueError, TypeError):
                return MATRIX_MIN_DIM
        cfg = {'cols': _dim('cols'), 'rows': _dim('rows')}
        for k in ('x_label', 'y_label', 'x_low', 'x_high', 'y_low', 'y_high'):
            v = str(src.get(k) or '').strip()[:MAX_AXIS_LABEL_LEN]
            if v:
                cfg[k] = v
        return (cfg, None)
    if q_type == 'scatter':
        cfg = {}
        # End labels name what each end of an axis means ("Cheap" … "Expensive");
        # without them the audience only sees 0 and 100.
        for k in ('x_label', 'y_label', 'x_low', 'x_high', 'y_low', 'y_high'):
            v = str(src.get(k) or '').strip()[:MAX_AXIS_LABEL_LEN]
            if v:
                cfg[k] = v
        cfg['allow_color'] = bool(src.get('allow_color'))
        cfg['allow_size'] = bool(src.get('allow_size'))
        # Faint lines through the middle so a 2×2-style question reads as quadrants.
        cfg['quadrants'] = bool(src.get('quadrants'))
        return (cfg, None)
    # word_cloud, short_answer carry no config
    return ({}, None)


def parse_question_payload(data):
    """Validate/normalise an add/edit question payload.

    Returns (error_message_or_None, q_type, title, options_value)."""
    if not isinstance(data, dict):
        return ('Invalid request body.', None, None, None)
    q_type = data.get('type')
    if not isinstance(q_type, str) or q_type not in VALID_QUESTION_TYPES:
        return ('Invalid question type.', None, None, None)
    title = data.get('title')
    title = title.strip() if isinstance(title, str) else ''
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
                                         'multiple_choice_other', 'image_choice', 'emoji')
                              and isinstance(parsed, list)) else [],
        'max_rating': 5,
    }
    if q.type in ('matrix', 'scatter') and isinstance(parsed, dict):
        data['options'] = parsed
    if q.type == 'rating' and isinstance(parsed, dict):
        try:
            data['max_rating'] = int(parsed.get('max_rating', 5))
        except (ValueError, TypeError):
            data['max_rating'] = 5
    if q.type == 'numeric' and isinstance(parsed, dict):
        data['numeric'] = {k: parsed[k] for k in ('min', 'max', 'step') if k in parsed}
    return data


def _axis_position(label, pos, n, low, high, default_name):
    """Describe where `pos` (1 = low end) sits on an n-step axis, in the
    presenter's own words where they gave them: "Impact: high"."""
    if pos == 1:
        where = low or 'low'
    elif pos == n:
        where = high or 'high'
    else:
        where = 'middle' if n == 3 else f'{pos} of {n}'
    return f'{label or default_name}: {where}'


def response_display_label(q_type, value, options=None):
    """Human-readable version of a stored response_value for status lines.

    Matrix cells ("2,1") and scatter points (JSON) are meaningless raw; every
    other type already reads fine as-is. `options` is the question's parsed
    config, used to name matrix positions with the axis labels.
    """
    if value is None:
        return ''
    if q_type == 'matrix':
        cfg = options if isinstance(options, dict) else {}
        try:
            c, r = (int(v) for v in str(value).split(','))
            cols = int(cfg.get('cols', 2))
            rows = int(cfg.get('rows', 2))
        except (ValueError, TypeError):
            return str(value)
        # Rows are stored top-first (row 1 is the top of the grid), but the
        # grid reads like a chart (low at the bottom), so count up from there.
        x = _axis_position(cfg.get('x_label'), c, cols, cfg.get('x_low'), cfg.get('x_high'),
                           'Horizontal')
        y = _axis_position(cfg.get('y_label'), rows - r + 1, rows, cfg.get('y_low'),
                           cfg.get('y_high'), 'Vertical')
        return f'{x}, {y}'
    if q_type == 'ranking':
        return ', '.join(f'{i}. {opt}' for i, opt in enumerate(str(value).split('\n'), 1))
    if q_type == 'multi_select':
        return ', '.join(str(value).split('\n'))
    if q_type == 'scatter':
        try:
            p = json.loads(value)
            x = round(float(p.get('x', 0)))
            y = round(float(p.get('y', 0)))
            label = f'({x}, {y})'
            extras = [e for e in (p.get('c'), p.get('s')) if e]
            return f'{label} {" ".join(extras)}' if extras else label
        except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
            return str(value)
    return str(value)


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

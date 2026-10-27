"""Per-question result statistics used by the live views and exports."""

import json
import math
from typing import Any, Dict

from .extensions import db
from .models import Question, Response
from .questions import parsed_options

# Basic English stop words list (can be expanded)
STOP_WORDS = frozenset([
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't", "as", "at",
    "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd",
    "he'll", "he's", "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself",
    "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out",
    "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these", "they",
    "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too", "under", "until", "up", "very",
    "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's",
    "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't",
    "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
])


def _word_counts(responses):
    words = {}
    for resp in responses:
        for word in str(resp.response_value).lower().split():
            cleaned_word = ''.join(filter(str.isalnum, word))
            if cleaned_word and cleaned_word not in STOP_WORDS:
                words[cleaned_word] = words.get(cleaned_word, 0) + 1
    return words


def _options_list(question):
    """The question's options as a list (choice-style types), or []."""
    parsed = parsed_options(question)
    return parsed if isinstance(parsed, list) else []


def _options_dict(question):
    """The question's config as a dict (rating/numeric/matrix/scatter), or {}."""
    parsed = parsed_options(question)
    return parsed if isinstance(parsed, dict) else {}


def get_question_stats(question_id: int) -> Dict[str, Any]:
    """Gets statistics for a question based on its type."""
    question = db.session.get(Question, question_id)
    if not question:
        return {"error": "Question not found"}

    all_responses = Response.query.filter_by(question_id=question_id).all()
    total_responses = len(all_responses)
    stats: Dict[str, Any] = {"total_responses": total_responses,
                             "type": question.type, "title": question.title}

    if question.type == 'multiple_choice':
        options = [str(opt) for opt in _options_list(question)]
        results = dict.fromkeys(options, 0)
        for resp in all_responses:
            if str(resp.response_value) in results:
                results[str(resp.response_value)] += 1
        stats["results"] = results
        stats["options"] = options

    elif question.type == 'word_cloud':
        stats["results"] = [{"text": w, "weight": c} for w, c in _word_counts(all_responses).items()]

    elif question.type == 'rating':
        try:
            max_rating = int(_options_dict(question).get('max_rating', 5))
        except (ValueError, TypeError):
            max_rating = 5
        results = {str(i): 0 for i in range(1, max_rating + 1)}
        for resp in all_responses:
            if str(resp.response_value) in results:
                results[str(resp.response_value)] += 1
        stats["results"] = results
        stats["max_rating"] = max_rating

    elif question.type == 'multi_select':
        options = [str(o) for o in _options_list(question)]
        results = dict.fromkeys(options, 0)
        for resp in all_responses:
            for sel in str(resp.response_value).split('\n'):
                if sel in results:
                    results[sel] += 1
        stats["results"] = results
        stats["options"] = options

    elif question.type == 'short_answer':
        answers = []
        for resp in all_responses:
            text = str(resp.response_value).strip()
            if text:
                answers.append({"text": text, "ts": resp.created_at})
        answers.sort(key=lambda a: a.get("ts") or "", reverse=True)
        stats["results"] = answers  # list of {text, ts}, newest first — drives the answers view
        stats["cloud"] = [{"text": w, "weight": c}
                          for w, c in _word_counts(all_responses).items()]  # for the cloud toggle

    elif question.type == 'ranking':
        options = [str(o) for o in _options_list(question)]
        sums, counts = dict.fromkeys(options, 0.0), dict.fromkeys(options, 0)
        for resp in all_responses:
            for pos, opt in enumerate(str(resp.response_value).split('\n'), 1):
                if opt in sums:
                    sums[opt] += pos
                    counts[opt] += 1
        stats["results"] = {o: (round(sums[o] / counts[o], 2) if counts[o] else 0) for o in options}
        stats["options"] = options

    elif question.type == 'numeric':
        vals = []
        for resp in all_responses:
            try:
                v = float(resp.response_value)
            except (ValueError, TypeError):
                continue
            # Skip NaN/inf stored before the audience route rejected them:
            # one would make the average NaN, which isn't valid JSON.
            if math.isfinite(v):
                vals.append(v)
        cfg = _options_dict(question)
        lo = hi = None
        if 'min' in cfg and 'max' in cfg:
            try:
                lo, hi = float(cfg['min']), float(cfg['max'])
            except (ValueError, TypeError):
                lo = hi = None
            if lo is not None and not (math.isfinite(lo) and math.isfinite(hi)):
                lo = hi = None
        if lo is None and vals:
            lo, hi = min(vals), max(vals)
        results = {}
        if vals and lo is not None and hi is not None and hi > lo:
            nb, step = 10, (hi - lo) / 10

            def _lbl(x):
                return f"{x:.1f}".rstrip('0').rstrip('.') if not float(x).is_integer() else str(int(x))
            for i in range(nb):
                a, b = lo + i * step, lo + (i + 1) * step
                key = f"{_lbl(a)}–{_lbl(b)}"
                results[key] = sum(1 for v in vals if a <= v < b or (i == nb - 1 and v == b))
        elif vals:
            results[str(vals[0])] = len(vals)
        stats["results"] = results
        if vals:
            stats["average"] = round(sum(vals) / len(vals), 2)

    elif question.type == 'image_choice':
        labels = [str(it.get('label', '')) for it in _options_list(question)
                  if isinstance(it, dict)]
        results = dict.fromkeys(labels, 0)
        for resp in all_responses:
            v = str(resp.response_value)
            if v in results:
                results[v] += 1
        stats["results"] = results
        stats["options"] = labels

    elif question.type == 'emoji':
        emojis = [str(e) for e in _options_list(question)]
        results = dict.fromkeys(emojis, 0)
        for resp in all_responses:
            v = str(resp.response_value)
            if v in results:
                results[v] += 1
        stats["results"] = results
        stats["options"] = emojis

    elif question.type == 'matrix':
        cfg = _options_dict(question)
        try:
            cols = max(1, min(10, int(cfg.get('cols', 2))))
            rows = max(1, min(10, int(cfg.get('rows', 2))))
        except (ValueError, TypeError):
            cols = rows = 2
        results = {f"{c},{r}": 0 for c in range(1, cols + 1) for r in range(1, rows + 1)}
        for resp in all_responses:
            v = str(resp.response_value)
            if v in results:
                results[v] += 1
        stats["results"] = results
        stats["grid"] = {"cols": cols, "rows": rows,
                         **{k: cfg[k] for k in
                            ('x_label', 'y_label', 'x_low', 'x_high', 'y_low', 'y_high')
                            if cfg.get(k)}}

    elif question.type == 'scatter':
        cfg = _options_dict(question)
        points = []
        for resp in all_responses:
            try:
                p = json.loads(resp.response_value)
                pt = {"x": float(p["x"]), "y": float(p["y"])}
            except (json.JSONDecodeError, TypeError, ValueError, KeyError):
                continue
            if not (0 <= pt["x"] <= 100 and 0 <= pt["y"] <= 100):
                continue
            if p.get("c"):
                pt["c"] = str(p["c"])
            if p.get("s"):
                pt["s"] = str(p["s"])
            points.append(pt)
        stats["points"] = points
        stats["config"] = {"x_label": cfg.get("x_label", ""), "y_label": cfg.get("y_label", ""),
                           "allow_color": bool(cfg.get("allow_color")),
                           "allow_size": bool(cfg.get("allow_size"))}

    elif question.type == 'multiple_choice_other':
        options = [str(o) for o in _options_list(question)]
        labels = options + ['Other']
        results = dict.fromkeys(labels, 0)
        for resp in all_responses:
            v = str(resp.response_value)
            if v in options:
                results[v] += 1
            else:
                results['Other'] += 1
        stats["results"] = results
        stats["options"] = labels

    return stats

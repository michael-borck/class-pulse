"""Per-question result statistics used by the live views and exports."""

import json
from typing import Any, Dict

from .extensions import db
from .models import Question, Response

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
        try:
            options = json.loads(question.options)
            if not isinstance(options, list):
                options = []
        except json.JSONDecodeError:
            options = []
        options = [str(opt) for opt in options]
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
            config = json.loads(question.options)
            max_rating = int(config.get('max_rating', 5))
        except (json.JSONDecodeError, AttributeError, ValueError):
            max_rating = 5
        results = {str(i): 0 for i in range(1, max_rating + 1)}
        for resp in all_responses:
            if str(resp.response_value) in results:
                results[str(resp.response_value)] += 1
        stats["results"] = results
        stats["max_rating"] = max_rating

    elif question.type == 'multi_select':
        try:
            options = [str(o) for o in (json.loads(question.options) if question.options else [])]
        except (json.JSONDecodeError, TypeError):
            options = []
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
        try:
            options = [str(o) for o in (json.loads(question.options) if question.options else [])]
        except (json.JSONDecodeError, TypeError):
            options = []
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
                vals.append(float(resp.response_value))
            except (ValueError, TypeError):
                pass
        try:
            cfg = json.loads(question.options) if question.options else {}
        except (json.JSONDecodeError, TypeError):
            cfg = {}
        lo = hi = None
        if isinstance(cfg, dict) and 'min' in cfg and 'max' in cfg:
            try:
                lo, hi = float(cfg['min']), float(cfg['max'])
            except (ValueError, TypeError):
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
        try:
            items = json.loads(question.options) if question.options else []
        except (json.JSONDecodeError, TypeError):
            items = []
        labels = [str(it.get('label', '')) for it in items] if isinstance(items, list) else []
        results = dict.fromkeys(labels, 0)
        for resp in all_responses:
            v = str(resp.response_value)
            if v in results:
                results[v] += 1
        stats["results"] = results
        stats["options"] = labels

    elif question.type == 'multiple_choice_other':
        try:
            options = [str(o) for o in (json.loads(question.options) if question.options else [])]
        except (json.JSONDecodeError, TypeError):
            options = []
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

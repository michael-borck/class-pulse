"""Moderation pipeline for audience-proposed questions (cohort mode).

Three tiers, cheapest first. Nothing is silently discarded: a tripped filter
sets status='flagged' so the proposal is hidden from the public list until the
presenter approves or rejects it — the presenter always has the final say.

1. Keyword filter — always on, instant, offline. Built-in profanity list,
   extendable one-term-per-line via instance/moderation_keywords.txt.
2. Similarity — flags nothing; attaches a "similar to #N" hint so voters and
   the presenter can spot near-duplicates.
3. LLM check — only when AI is configured (reuses the ai.py adapter). If the
   AI call errors, the proposal is flagged (not rejected) with a clear reason,
   so a broken provider never lets content through unreviewed.
"""

import json
import os
import re
from difflib import SequenceMatcher
from typing import Optional, Tuple

from flask import current_app

from . import ai
from .models import Proposal
from .stats import STOP_WORDS

# Unambiguous profanity/slurs only — subject terms that could appear in a real
# lesson (anatomy, drugs, war, ...) deliberately stay off this list; the LLM
# tier and the presenter handle context. Extend via instance/moderation_keywords.txt.
DEFAULT_BLOCKLIST = frozenset({
    "fuck", "fucking", "fucker", "motherfucker", "shit", "bullshit", "bitch",
    "cunt", "cock", "dick", "dildo", "pussy", "asshole", "arsehole", "wanker",
    "slut", "whore", "handjob", "blowjob", "cumshot", "jizz", "tits",
    "faggot", "fag", "nigger", "nigga", "retard", "retarded", "tranny",
    "kike", "spic", "wetback", "chink",
    "porn", "porno", "pornhub", "hentai", "xxx", "nudes", "onlyfans",
})

# Cheap leetspeak normalisation so "sh1t"/"f@ck" still match.
_LEET = str.maketrans({'0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's',
                       '7': 't', '@': 'a', '$': 's', '!': 'i'})

SIMILARITY_THRESHOLD = 0.75


def _extra_keywords() -> frozenset:
    """Admin-supplied terms, one per line; missing file is fine."""
    path = os.path.join(current_app.instance_path, 'moderation_keywords.txt')
    try:
        with open(path, encoding='utf-8') as f:
            return frozenset(w.strip().lower() for w in f if w.strip()
                             and not w.startswith('#'))
    except OSError:
        return frozenset()


def _tokens(text: str):
    return re.findall(r"[a-z0-9@$!]+", (text or '').lower())


def keyword_flag(text: str) -> Optional[str]:
    """Return the matched blocklist term, or None if the text is clean."""
    blocklist = DEFAULT_BLOCKLIST | _extra_keywords()
    for tok in _tokens(text):
        if tok in blocklist:
            return tok
        normalised = tok.translate(_LEET)
        if normalised in blocklist:
            return normalised
    return None


def _significant_tokens(title: str) -> frozenset:
    return frozenset(t for t in re.findall(r"[a-z0-9]+", (title or '').lower())
                     if t not in STOP_WORDS)


def find_similar(session_id: int, title: str) -> Tuple[Optional[int], float]:
    """Best near-duplicate among the session's pending/approved proposals.

    Token-set Jaccard, backed up by a SequenceMatcher ratio for short titles
    where token overlap is too coarse. Returns (proposal_id or None, score).
    """
    mine = _significant_tokens(title)
    best_id, best_score = None, 0.0
    candidates = Proposal.query.filter(
        Proposal.session_id == session_id,
        Proposal.status.in_(('visible', 'flagged', 'approved')),
    ).all()
    for p in candidates:
        theirs = _significant_tokens(p.title)
        if mine and theirs:
            union = mine | theirs
            jaccard = len(mine & theirs) / len(union) if union else 0.0
        else:
            jaccard = 0.0
        ratio = SequenceMatcher(None, (title or '').lower(), p.title.lower()).ratio()
        score = max(jaccard, ratio)
        if score > best_score:
            best_id, best_score = p.id, score
    if best_score >= SIMILARITY_THRESHOLD:
        return best_id, best_score
    return None, best_score


_LLM_PROMPT = """You are the content moderator for a classroom audience-response tool.
Students anonymously propose questions for the class to vote on. Flag anything
inappropriate for a classroom screen: sexual/NSFW content, harassment or hate,
slurs, doxxing, spam, or pranks with no plausible educational intent. Ordinary
academic topics (anatomy, drugs, war, crime, religion...) are FINE when asked
in good faith. When unsure, prefer ok=true — a human presenter reviews flags.

Proposed question:
- Title: {title}
- Options: {options}

Respond with JSON only:
{{"ok": true/false, "reason": "one short phrase if not ok, else null"}}"""


def llm_flag(title: str, options_text: str) -> Tuple[bool, Optional[str]]:
    """(ok, reason). Errors flag for review rather than letting content through."""
    if not ai.AI_ENABLED:
        return True, None
    result = ai.call_ai(_LLM_PROMPT.format(title=title, options=options_text or 'none'))
    if not result.get("success"):
        current_app.logger.warning(f"Proposal LLM check failed: {result.get('error')}")
        return False, "AI check unavailable — needs manual review"
    try:
        match = re.search(r'\{.*\}', result["response"], re.DOTALL)
        data = json.loads(match.group()) if match else {}
        if data.get("ok") is True:
            return True, None
        reason = str(data.get("reason") or "flagged by AI check")[:150]
        return False, f"AI check: {reason}"
    except Exception:
        current_app.logger.warning("Proposal LLM check returned unparseable output")
        return False, "AI check unreadable — needs manual review"


def moderate_proposal(session_id: int, title: str, options_text: str) -> dict:
    """Run the pipeline. Returns {'status', 'flag_reason', 'similar_to_id'}."""
    full_text = f"{title}\n{options_text or ''}"
    similar_to_id, _score = find_similar(session_id, title)

    matched = keyword_flag(full_text)
    if matched:
        return {'status': 'flagged',
                'flag_reason': f'keyword filter matched "{matched}"',
                'similar_to_id': similar_to_id}

    ok, reason = llm_flag(title, options_text)
    if not ok:
        return {'status': 'flagged', 'flag_reason': reason,
                'similar_to_id': similar_to_id}

    return {'status': 'visible', 'flag_reason': None, 'similar_to_id': similar_to_id}

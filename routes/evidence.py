"""
routes/evidence.py — read-only spelling headline data for external
aggregators (the DOOYA tracker's evidence pull, see wfa-data's
routers/evidence.py). Token-gated like every other cross-tool call in
this ecosystem's server-to-server integrations (reading-tracker,
writing-tracker, RTP tracker) — deliberately NOT the human session
password (APP_PASSWORD), since a server calling this has no browser
session to hold that cookie. Read-only: nothing here ever writes.
"""

import os

from flask import Blueprint, jsonify, request

import word_bank
from data_manager import _resolve_classes, load_class, latest_rule_confidence_entry, stuck_key_spellings

evidence_bp = Blueprint('evidence', __name__)

# Optional extra machine token, from the environment only (no default in code).
# The Tracker calls this route with the hub token.
EVIDENCE_TOKEN = os.environ.get('EVIDENCE_TOKEN', '')


def _evidence_token_ok(token):
    """Accept the hub token (HUB_TOKEN setting) or the dedicated evidence token."""
    import hmac
    token = token or ''
    for good in (os.environ.get('HUB_TOKEN') or '', EVIDENCE_TOKEN or ''):
        if good and hmac.compare_digest(token.encode(), good.encode()):
            return True
    return False

_SUPPORTED_YEARS = {'Y1', 'Y2', 'Y3', 'Y4', 'Y5', 'Y6'}  # word bank has no real Reception content


@evidence_bp.route('/api/evidence/spelling/<year_group>')
def spelling_evidence(year_group):
    if not _evidence_token_ok(request.args.get('token')):
        return jsonify({'error': 'unauthorised'}), 401
    if year_group not in _SUPPORTED_YEARS:
        return jsonify({'spelling': {}})

    class_ids = _resolve_classes(f'{year_group}_all')
    result = {}
    by_code = {}     # keyed by the pupil code (roster pupil_id): lets the Tracker join without any UPN
    for cid in class_ids:
        data = load_class(cid)
        if not data:
            continue
        for p in data.get('pupils', []):
            upn = (p.get('upn') or '').strip()
            code = (p.get('pupil_id') or '').strip()
            if not upn and not code:
                continue

            mastered_set = set(p.get('mastered') or [])
            stats = word_bank.mastery_stats(mastered_set)
            mastered_pct = stats.get(year_group)

            rc = p.get('rule_confidence') or {}
            scores = []
            for entries in rc.values():
                latest = latest_rule_confidence_entry(entries)
                if latest and latest.get('score') is not None:
                    scores.append(latest['score'])
            rule_confidence_pct = round(sum(scores) / len(scores)) if scores else None

            entry = {
                'mastered_pct': mastered_pct,
                'rule_confidence_pct': rule_confidence_pct,
            }
            if upn:
                result[upn] = entry
            if code:
                by_code[code] = entry

    return jsonify({'spelling': result, 'spelling_by_code': by_code})


@evidence_bp.route('/api/evidence/stuck-spellings/<year_group>')
def stuck_spellings_evidence(year_group):
    """Stuck key spellings per pupil code, for the Writing Targets tool (wfa-data calls this with the
    hub token). Words only: no names, no UPNs."""
    if not _evidence_token_ok(request.args.get('token')):
        return jsonify({'error': 'unauthorised'}), 401
    if year_group not in _SUPPORTED_YEARS:
        return jsonify({'by_code': {}})
    try:
        min_weeks = max(1, min(10, int(request.args.get('min_weeks', 2))))
    except ValueError:
        min_weeks = 2
    by_code = {}
    for row in stuck_key_spellings(f'{year_group}_all', min_weeks):
        if row.get('pupil_id'):
            by_code[row['pupil_id']] = [{'word': w['word'], 'n': w['n']} for w in row['words']]
    return jsonify({'by_code': by_code})

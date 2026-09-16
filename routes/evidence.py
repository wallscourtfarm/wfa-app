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
from data_manager import _resolve_classes, load_class, latest_rule_confidence_entry

evidence_bp = Blueprint('evidence', __name__)

# Distinct from APP_PASSWORD (human login) — a dedicated machine token for
# server-to-server calls, same convention as every Apps Script tool's
# SHARED_TOKEN. Set EVIDENCE_TOKEN as a real Render env var when convenient;
# this default is only a starting point, not meant to be the long-term value.
EVIDENCE_TOKEN = os.environ.get('EVIDENCE_TOKEN', 'wfa-app-evidence-16092026')

_SUPPORTED_YEARS = {'Y1', 'Y2', 'Y3', 'Y4', 'Y5', 'Y6'}  # word bank has no real Reception content


@evidence_bp.route('/api/evidence/spelling/<year_group>')
def spelling_evidence(year_group):
    if request.args.get('token') != EVIDENCE_TOKEN:
        return jsonify({'error': 'unauthorised'}), 401
    if year_group not in _SUPPORTED_YEARS:
        return jsonify({'spelling': {}})

    class_ids = _resolve_classes(f'{year_group}_all')
    result = {}
    for cid in class_ids:
        data = load_class(cid)
        if not data:
            continue
        for p in data.get('pupils', []):
            upn = (p.get('upn') or '').strip()
            if not upn:
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

            result[upn] = {
                'mastered_pct': mastered_pct,
                'rule_confidence_pct': rule_confidence_pct,
            }

    return jsonify({'spelling': result})

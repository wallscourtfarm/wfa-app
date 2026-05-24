from flask import Blueprint, render_template, session, redirect, url_for, request
from data_manager import load_class, ALL_CLASSES
from spelling_rules import SPELLING_RULES
from word_bank import WORD_BANK

insights_bp = Blueprint('insights', __name__)
CLASS_OPTIONS = [('all', 'Y4 ALL'), ('Y4_IM', 'Y4 IM'), ('Y4_WU', 'Y4 WU')]

WB_ZONES = [
    {'yr': 'R',    'label': 'Reception', 'start': 0,   'end': 20},
    {'yr': '1',    'label': 'Year 1',    'start': 21,  'end': 77},
    {'yr': '2',    'label': 'Year 2',    'start': 78,  'end': 130},
    {'yr': '3',    'label': 'Year 3',    'start': 131, 'end': 184},
    {'yr': '4',    'label': 'Year 4',    'start': 185, 'end': 238},
    {'yr': '5',    'label': 'Year 5',    'start': 239, 'end': 289},
    {'yr': '6',    'label': 'Year 6',    'start': 290, 'end': 343},
    {'yr': 'Post', 'label': 'Post-KS2', 'start': 344, 'end': 629},
]

HOMOPHONE_WORDS_BY_STAGE = {}
for r in SPELLING_RULES:
    if r[4] != 0: continue
    if 'homophone' not in r[2].lower() and 'near-homophone' not in r[2].lower(): continue
    HOMOPHONE_WORDS_BY_STAGE.setdefault(r[0], []).extend(r[3])

STAGE_LABEL = {2: 'Stage 2 (Y2)', 3: 'Stage 3 (Y3)', 4: 'Stage 4 (Y4)', 5: 'Stage 5 (Y5)'}

RULE_TITLE_MAP = {f'{r[0]}-{r[1]}': r[2] for r in SPELLING_RULES}


def _load_pupils(cls):
    if cls == 'all':
        pupils = []
        for cid in ALL_CLASSES:
            d = load_class(cid)
            if d: pupils.extend(d.get('pupils', []))
        return pupils
    d = load_class(cls)
    return d.get('pupils', []) if d else []


def _rule_priorities(pupils):
    """Per-rule: how many pupils, breakdown by status, average score. Sorted by impact."""
    rules = {}
    for p in pupils:
        for rid, entries in p.get('rule_confidence', {}).items():
            if not entries: continue
            latest = entries[-1]
            if rid not in rules:
                rules[rid] = {
                    'rule_id': rid,
                    'title': RULE_TITLE_MAP.get(rid, latest.get('rule', rid)),
                    'full': 0, 'partial': 0, 'none': 0,
                    'total_score': 0, 'n': 0,
                }
            rules[rid][latest.get('status', 'none')] += 1
            rules[rid]['total_score'] += latest.get('score', 0)
            rules[rid]['n'] += 1

    result = []
    for r in rules.values():
        n   = r['n']
        avg = round(r['total_score'] / n * 100) if n else 0
        result.append({**r, 'avg_pct': avg,
                        'needs_work': r['partial'] + r['none']})

    # Sort: most pupils needing work first, then lowest average
    return sorted(result, key=lambda x: (-x['needs_work'], x['avg_pct']))


def _homophone_gaps(pupils):
    """Per-word: mastered count, assessed count, %. Sorted by worst gap first."""
    n_total = len(pupils)
    hm_sets  = [set(w.lower() for w in p.get('homophone_mastered', []))
                for p in pupils]
    # Only count pupils who've done any homophone assessment
    assessed = [p for p in pupils if p.get('homophone_history')]
    n_assessed = len(assessed)
    assessed_hm = [set(w.lower() for w in p.get('homophone_mastered', []))
                   for p in assessed]

    if not n_assessed:
        return [], 0

    rows = []
    for stage in sorted(HOMOPHONE_WORDS_BY_STAGE):
        for word in HOMOPHONE_WORDS_BY_STAGE[stage]:
            w = word.lower()
            mastered = sum(1 for hm in assessed_hm if w in hm)
            pct      = round(mastered / n_assessed * 100)
            rows.append({
                'word':       word,
                'stage':      STAGE_LABEL.get(stage, f'Stage {stage}'),
                'mastered':   mastered,
                'assessed':   n_assessed,
                'pct':        pct,
                'gap_pct':    100 - pct,
            })

    return sorted(rows, key=lambda x: x['pct']), n_assessed


def _spelling_spread(pupils):
    """Distribution of pupils across word bank zones."""
    n = len(pupils)
    zones = []
    for z in WB_ZONES:
        count = sum(1 for p in pupils
                    if z['start'] <= p.get('word_pos', 0) <= z['end'])
        if count == 0 and z['yr'] not in ('R', '1', '2', '3', '4', '5', '6'):
            continue
        zones.append({**z, 'count': count,
                      'pct': round(count / n * 100) if n else 0})

    positions = sorted(p.get('word_pos', 0) for p in pupils)
    median_pos = positions[len(positions) // 2] if positions else 0
    # Find median zone
    median_zone = next(
        (z['label'] for z in WB_ZONES if z['start'] <= median_pos <= z['end']),
        'Unknown')

    return zones, median_pos, median_zone, n


@insights_bp.route('/insights')
def insights():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))
    cls = request.args.get('cls', 'all')
    if cls not in [c[0] for c in CLASS_OPTIONS]:
        cls = 'all'
    pupils = _load_pupils(cls)
    n = len(pupils)

    rule_rows          = _rule_priorities(pupils)
    homophone_rows, n_assessed = _homophone_gaps(pupils)
    zones, median_pos, median_zone, _ = _spelling_spread(pupils)

    return render_template('insights.html',
        cls=cls, class_options=CLASS_OPTIONS, n_pupils=n,
        rule_rows=rule_rows, rule_count=len(rule_rows),
        homophone_rows=homophone_rows, n_assessed=n_assessed,
        zones=zones, median_pos=median_pos, median_zone=median_zone)

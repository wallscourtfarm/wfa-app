from flask import Blueprint, render_template, session, redirect, url_for, request
from data_manager import load_class, ALL_CLASSES, get_class_options, get_class_options_for_year, get_ref_class
from spelling_rules import SPELLING_RULES
from word_bank import WORD_BANK

insights_bp = Blueprint('insights', __name__)
CLASS_OPTIONS = get_class_options()

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
    from data_manager import _resolve_classes
    pupils = []
    for cid in _resolve_classes(cls):
        d = load_class(cid)
        if d:
            pupils.extend(d.get('pupils', []))
    return pupils


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
    yr  = session.get('year_group', '4')
    cls = request.args.get('cls', f'Y{yr}_all')
    if cls not in [c[0] for c in get_class_options_for_year(session.get('year_group','4'))]:
        cls = 'all'
    pupils = _load_pupils(cls)
    n = len(pupils)

    rule_rows          = _rule_priorities(pupils)
    homophone_rows, n_assessed = _homophone_gaps(pupils)
    zones, median_pos, median_zone, _ = _spelling_spread(pupils)

    return render_template('insights.html',
        cls=cls, class_options=get_class_options_for_year(session.get("year_group","4")), n_pupils=n,
        rule_rows=rule_rows, rule_count=len(rule_rows),
        homophone_rows=homophone_rows, n_assessed=n_assessed,
        zones=zones, median_pos=median_pos, median_zone=median_zone)


# ── API: AI-generated actions ─────────────────────────────────────────────────

import os as _os, json as _json, re as _re
import requests as _requests

@insights_bp.route('/api/insights/actions', methods=['POST'])
def api_insights_actions():
    from flask import request, jsonify
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401

    cls = request.get_json(force=True).get('cls', 'all')
    pupils = _load_pupils(cls)
    if not pupils:
        return jsonify({'ok': False, 'error': 'No pupils found'})

    rule_rows                  = _rule_priorities(pupils)
    homophone_rows, n_assessed = _homophone_gaps(pupils)
    zones, median_pos, median_zone, _ = _spelling_spread(pupils)

    n_pupils  = len(pupils)
    yr = session.get('year_group', '4')
    _opts = {v: l for v, l in get_class_options_for_year(yr)}
    cls_label = _opts.get(cls, cls)

    rule_lines = [
        f"  {r['rule_id']} {r['title']}: {r['n']}/{n_pupils} assessed, "
        f"{r['full']} full / {r['partial']} partial / {r['none']} not yet, avg {r['avg_pct']}%"
        for r in rule_rows[:8]
    ]
    hom_lines = [
        f"  \'{h['word']}\' ({h['stage']}): {h['mastered']}/{h['assessed']} mastered ({h['pct']}%)"
        for h in homophone_rows[:10]
    ]
    zone_lines = [
        f"  {z['label']} (words {z['start']}\u2013{z['end']}): {z['count']} pupils"
        for z in zones if z['count']
    ]

    prompt = f"""You are an experienced UK primary school teaching advisor.
A Year 4 teacher has shared assessment data for their class ({cls_label}, {n_pupils} pupils).
Generate exactly 5 specific, prioritised actions to have the biggest impact on spelling outcomes.

CLASS DATA:

Rule confidence (worst first):
{chr(10).join(rule_lines) if rule_lines else "  No rule assessments yet."}

Homophone gaps (worst mastery first, {n_assessed} pupils assessed):
{chr(10).join(hom_lines) if hom_lines else "  No homophone assessments yet."}

Key spelling spread (word bank position):
{chr(10).join(zone_lines)}
Median pupil: word {median_pos}/630 ({median_zone})

INSTRUCTIONS:
- Each action must be specific and tied directly to the data above
- Refer to actual rule IDs, word names, or zones — no vague generalities
- Order by highest impact first
- British English throughout
- Return ONLY a JSON array of 5 objects with keys: "title" (max 8 words), "action" (one concrete sentence), "rationale" (one data-backed sentence)
- No preamble, no markdown fences, no extra text"""

    api_key = _os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return jsonify({'ok': False, 'error': 'ANTHROPIC_API_KEY not set'})

    resp = _requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={'x-api-key': api_key, 'anthropic-version': '2023-06-01',
                 'content-type': 'application/json'},
        json={'model': 'claude-sonnet-4-5', 'max_tokens': 1200,
              'messages': [{'role': 'user', 'content': prompt}]},
        timeout=30,
    )

    if resp.status_code != 200:
        return jsonify({'ok': False, 'error': f'API error {resp.status_code}'})

    text = resp.json()['content'][0]['text'].strip()
    text = _re.sub(r'^```[a-z]*\n?', '', text)
    text = _re.sub(r'\n?```$', '', text)

    try:
        actions = _json.loads(text)
        return jsonify({'ok': True, 'actions': actions, 'cls': cls_label})
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Parse error: {e}', 'raw': text})


# ── API: Actions PDF ──────────────────────────────────────────────────────────

from reportlab.pdfgen import canvas as _rl_canvas
from reportlab.lib.pagesizes import A4 as _A4
from reportlab.lib.units import mm as _mm
from reportlab.lib.utils import simpleSplit as _simpleSplit
import io as _io
from datetime import date as _date

@insights_bp.route('/api/insights/actions-pdf', methods=['POST'])
def api_insights_actions_pdf():
    from flask import request, send_file
    if not session.get('authenticated'):
        return {'error': 'Not authenticated'}, 401

    body     = request.get_json(force=True)
    actions  = body.get('actions', [])
    cls_lbl  = body.get('cls', 'Y4')
    today    = _date.today().strftime('%d %B %Y')

    buf = _io.BytesIO()
    W, H = _A4
    M    = 18 * _mm

    c = _rl_canvas.Canvas(buf, pagesize=_A4)

    # ── Header bar ────────────────────────────────────────────────────────────
    HDR = 16 * _mm
    c.setFillColorRGB(0.30, 0.30, 0.30)
    c.rect(0, H - HDR, W, HDR, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont('Helvetica-Bold', 12)
    c.drawString(M, H - HDR + (HDR - 12) / 2, 'Actions for Impact')
    c.setFont('Helvetica', 8)
    c.drawRightString(W - M, H - HDR + (HDR - 8) / 2,
                      f'{cls_lbl}  ·  Generated {today}')

    # ── Intro line ────────────────────────────────────────────────────────────
    y = H - HDR - 10 * _mm
    c.setFont('Helvetica-Oblique', 8.5)
    c.setFillColorRGB(0.40, 0.40, 0.40)
    c.drawString(M, y,
        'Five prioritised actions based on current class assessment data — highest impact first.')
    y -= 8 * _mm

    UW      = W - 2 * M
    PADDING = 4 * _mm

    for i, action in enumerate(actions[:5]):
        title    = action.get('title', '')
        act_text = action.get('action', '')
        rat_text = action.get('rationale', '')

        # Measure height needed for this action
        act_lines = _simpleSplit(act_text,  'Helvetica', 10, UW - 14 * _mm)
        rat_lines = _simpleSplit(rat_text,  'Helvetica', 8.5, UW - 14 * _mm)
        num_h     = 11 * _mm   # circle + title row
        body_h    = (len(act_lines) * 5 * _mm) + (len(rat_lines) * 4.5 * _mm) + 3 * _mm
        box_h     = num_h + body_h + 2 * PADDING

        if y - box_h < M:
            c.showPage()
            y = H - M

        # Card background
        c.setFillColorRGB(0.97, 0.97, 0.97)
        c.roundRect(M, y - box_h, UW, box_h, 3 * _mm, fill=1, stroke=0)

        # Number circle
        cx = M + PADDING + 4.5 * _mm
        cy = y - PADDING - 4.5 * _mm
        c.setFillColorRGB(0.20, 0.20, 0.20)
        c.circle(cx, cy, 4.5 * _mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont('Helvetica-Bold', 11)
        c.drawCentredString(cx, cy - 3.5, str(i + 1))

        # Title
        c.setFillColorRGB(0.10, 0.10, 0.10)
        c.setFont('Helvetica-Bold', 11)
        c.drawString(M + PADDING + 12 * _mm, cy - 3.5, title)

        # Action text
        text_x = M + PADDING + 3 * _mm
        text_y = y - PADDING - num_h
        c.setFillColorRGB(0.10, 0.10, 0.10)
        c.setFont('Helvetica', 10)
        for line in act_lines:
            c.drawString(text_x, text_y, line)
            text_y -= 5 * _mm

        # Rationale
        text_y -= 1 * _mm
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.setFont('Helvetica-Oblique', 8.5)
        for line in rat_lines:
            c.drawString(text_x, text_y, line)
            text_y -= 4.5 * _mm

        y -= box_h + 5 * _mm   # gap between cards

    c.save()
    buf.seek(0)

    filename = f'Actions_for_Impact_{cls_lbl.replace(" ", "_")}_{today.replace(" ", "_")}.pdf'
    return send_file(buf, mimetype='application/pdf',
                     as_attachment=True, download_name=filename)

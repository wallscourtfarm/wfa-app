import os
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from uls_lessons import ULS_LESSONS, get_lesson, get_week_lessons, get_all_weeks, TERM_LABELS
from data_manager import load_rule_confidence, save_rule_confidence

rules_bp = Blueprint('rules', __name__)

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

def _auth():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))


def _build_uls_tree(year_group, confidence):
    """Return nested structure: {term: {week: [lesson_dicts]}} for a year group."""
    tree = {}
    for l in ULS_LESSONS:
        if l['year'] != year_group:
            continue
        term = l['term']
        week = l['week']
        tree.setdefault(term, {}).setdefault(week, []).append({
            **l,
            'confidence': confidence.get(l['id'], {}).get('level', 0),
        })
    return tree


# ── Routes ────────────────────────────────────────────────────────────────────

@rules_bp.route('/rules')
def rules():
    r = _auth()
    if r: return r
    yr_str = session.get('year_group', '4')
    year_group = f'Y{yr_str}' if not yr_str.startswith('Y') else yr_str
    confidence = load_rule_confidence()
    tree = _build_uls_tree(year_group, confidence)
    return render_template('rules.html',
        tree=tree,
        term_labels=TERM_LABELS,
        year_group=year_group,
        all_years=['Y2','Y3','Y4','Y5','Y6'],
    )


@rules_bp.route('/rules/overview')
def rules_overview():
    r = _auth()
    if r: return r
    year_group = request.args.get('year', 'Y3')
    if not year_group.startswith('Y'):
        year_group = f'Y{year_group}'
    lessons = [l for l in ULS_LESSONS if l['year'] == year_group]
    lessons.sort(key=lambda l: (l['term'], l['week'], l['weekLesson']))
    return render_template('rules_overview.html',
        lessons=lessons,
        term_labels=TERM_LABELS,
        year_group=year_group,
        all_years=['Y2','Y3','Y4','Y5','Y6'],
    )


@rules_bp.route('/api/rules/confidence', methods=['POST'])
def api_confidence():
    if not session.get('authenticated'):
        return jsonify({'ok': False}), 401
    body = request.get_json(force=True)
    lesson_id = body.get('lesson_id', '') or body.get('rule_id', '')
    level     = int(body.get('level', 0))
    if not lesson_id or level not in (0, 1, 2, 3):
        return jsonify({'ok': False, 'error': 'Bad input'})
    conf = load_rule_confidence()
    conf[lesson_id] = {'level': level}
    ok = save_rule_confidence(conf)
    return jsonify({'ok': ok})


@rules_bp.route('/api/rules/lesson')
def api_lesson():
    if not session.get('authenticated'):
        return jsonify({'ok': False}), 401
    lid = request.args.get('id', '')
    l = get_lesson(lid)
    if not l:
        return jsonify({'ok': False, 'error': 'Not found'})
    return jsonify({'ok': True, 'lesson': l})

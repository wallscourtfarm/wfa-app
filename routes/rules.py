import os, json, datetime
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from spelling_rules import SPELLING_RULES
from data_manager import (
    load_custom_rules, save_custom_rules,
    load_rule_confidence, save_rule_confidence
)

rules_bp = Blueprint('rules', __name__)

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

def _auth():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))

# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_stages():
    """Return standard rules grouped by stage, with confidence merged in."""
    confidence = load_rule_confidence()
    stages = {}
    for r in SPELLING_RULES:
        stage, step, title, words, rtype = r
        if rtype == 1:  # skip Challenge Words
            continue
        rid = f'{stage}-{step}'
        stages.setdefault(stage, []).append({
            'id':         rid,
            'step':       step,
            'title':      title,
            'words':      words,
            'rtype':      rtype,
            'confidence': confidence.get(rid, {}).get('level', 0),
        })
    return stages

def _build_custom():
    """Return custom rules with confidence merged in."""
    confidence = load_rule_confidence()
    rules = load_custom_rules()
    result = []
    for cr in rules:
        rid = f'0-{cr["id"]}'
        result.append({**cr, 'confidence': confidence.get(rid, {}).get('level', 0)})
    return result

# ── Routes ────────────────────────────────────────────────────────────────────

@rules_bp.route('/rules')
def rules():
    r = _auth()
    if r: return r
    stages  = _build_stages()
    customs = _build_custom()
    return render_template('rules.html', stages=stages, customs=customs)


@rules_bp.route('/api/rules/confidence', methods=['POST'])
def api_confidence():
    if not session.get('authenticated'):
        return jsonify({'ok': False}), 401
    body = request.get_json(force=True)
    rule_id = body.get('rule_id', '')
    level   = int(body.get('level', 0))
    if not rule_id or level not in (0, 1, 2, 3):
        return jsonify({'ok': False, 'error': 'Bad input'})
    conf = load_rule_confidence()
    conf[rule_id] = {'level': level}
    ok = save_rule_confidence(conf)
    return jsonify({'ok': ok})


@rules_bp.route('/api/rules/custom/add', methods=['POST'])
def api_custom_add():
    if not session.get('authenticated'):
        return jsonify({'ok': False}), 401
    body  = request.get_json(force=True)
    title = body.get('title', '').strip()
    explanation = body.get('explanation', '').strip()
    words_raw   = body.get('words', '')
    words = [w.strip() for w in words_raw.split(',') if w.strip()]
    if not title or not words:
        return jsonify({'ok': False, 'error': 'Title and at least one word are required'})
    rules = load_custom_rules()
    next_id = max((cr['id'] for cr in rules), default=0) + 1
    new_rule = {
        'id':          next_id,
        'title':       title,
        'explanation': explanation,
        'words':       words,
        'created':     datetime.date.today().isoformat(),
    }
    rules.append(new_rule)
    ok = save_custom_rules(rules, next_id + 1)
    if ok:
        return jsonify({'ok': True, 'rule': {**new_rule, 'confidence': 0}})
    return jsonify({'ok': False, 'error': 'GitHub write failed'})


@rules_bp.route('/api/rules/custom/edit', methods=['POST'])
def api_custom_edit():
    if not session.get('authenticated'):
        return jsonify({'ok': False}), 401
    body  = request.get_json(force=True)
    rule_id = int(body.get('id', 0))
    title   = body.get('title', '').strip()
    explanation = body.get('explanation', '').strip()
    words_raw   = body.get('words', '')
    words = [w.strip() for w in words_raw.split(',') if w.strip()]
    if not title or not words:
        return jsonify({'ok': False, 'error': 'Title and at least one word are required'})
    rules = load_custom_rules()
    for i, cr in enumerate(rules):
        if cr['id'] == rule_id:
            rules[i] = {**cr, 'title': title, 'explanation': explanation, 'words': words}
            break
    else:
        return jsonify({'ok': False, 'error': 'Rule not found'})
    next_id = max((cr['id'] for cr in rules), default=0) + 1
    ok = save_custom_rules(rules, next_id)
    return jsonify({'ok': ok, 'error': None if ok else 'GitHub write failed'})


@rules_bp.route('/api/rules/custom/delete', methods=['POST'])
def api_custom_delete():
    if not session.get('authenticated'):
        return jsonify({'ok': False}), 401
    body    = request.get_json(force=True)
    rule_id = int(body.get('id', 0))
    rules   = load_custom_rules()
    before  = len(rules)
    rules   = [cr for cr in rules if cr['id'] != rule_id]
    if len(rules) == before:
        return jsonify({'ok': False, 'error': 'Rule not found'})
    next_id = max((cr['id'] for cr in rules), default=0) + 1
    # Also remove confidence entry
    conf = load_rule_confidence()
    conf.pop(f'0-{rule_id}', None)
    save_rule_confidence(conf)
    ok = save_custom_rules(rules, next_id)
    return jsonify({'ok': ok, 'error': None if ok else 'GitHub write failed'})


@rules_bp.route('/api/rules/suggest-words', methods=['POST'])
def api_suggest_words():
    if not session.get('authenticated'):
        return jsonify({'ok': False}), 401
    body  = request.get_json(force=True)
    title = body.get('title', '').strip()
    explanation = body.get('explanation', '').strip()
    if not title:
        return jsonify({'ok': False, 'error': 'Title is required'})
    import requests as req
    prompt = (
        f'You are a UK primary school spelling expert. '
        f'Generate exactly 5 good example words for the following spelling rule. '
        f'Rule title: {title}. '
        + (f'Explanation: {explanation}. ' if explanation else '')
        + 'Words should be appropriate for KS2 pupils (ages 7–11), clearly demonstrate the rule, '
        f'and be varied in difficulty. '
        f'Reply with ONLY a comma-separated list of 5 words, nothing else.'
    )
    try:
        resp = req.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 100,
                'messages': [{'role': 'user', 'content': prompt}],
            },
            timeout=30,
        )
        data = resp.json()
        text = data['content'][0]['text'].strip()
        words = [w.strip() for w in text.split(',') if w.strip()][:5]
        return jsonify({'ok': True, 'words': words})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

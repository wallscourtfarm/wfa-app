import base64
import io
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import load_class, load_weekly_config, get_rule, ALL_CLASSES
from word_bank import get_active_words

hl_bp = Blueprint('hl', __name__)
CLASS_OPTIONS = [('Y4_IM', 'Y4 IM'), ('Y4_WU', 'Y4 WU')]
COLUMN_KEYWORDS = {'column', 'addition', 'subtraction', 'written method'}


def _get_hl_pupils(pupils, version='standard'):
    if version == 'adapted':
        target = [p for p in pupils if p.get('adapted_hl', False)]
    else:
        target = [p for p in pupils if not p.get('adapted_hl', False)]
    def sort_key(p):
        cls_order = 0 if p.get('cls') == 'IM' else 1
        tbl = p.get('table', '')
        try: tbl_num = int(tbl) if tbl else 999
        except ValueError: tbl_num = 999
        return (cls_order, tbl_num, p.get('first', '').lower())
    return sorted(target, key=sort_key)


def _enforce_column_method(data):
    # If Q1-Q3 have parts a) and b), force column_method answer type
    questions = data.get('questions', [])
    changed = False
    for i, q in enumerate(questions[:3]):
        text = q.get('text', '').lower()
        if ' a)' in text and ' b)' in text:
            data['questions'][i]['answer_type'] = 'column_method'
            data['questions'][i]['answer_lines'] = 0
            changed = True
    if changed:
        data['grid_elements'] = []
        data['grid_size'] = 0
    return data


def _is_column_topic(maths_topic, maths_notes):
    combined = (maths_topic + ' ' + maths_notes).lower()
    return any(kw in combined for kw in COLUMN_KEYWORDS)


@hl_bp.route('/home-learning')
def home_learning():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))
    cls = request.args.get('cls', 'Y4_IM')
    if cls not in [c[0] for c in CLASS_OPTIONS]:
        cls = 'Y4_IM'
    wc = load_weekly_config()
    week_ref  = wc.get('week_ref', '')
    cls_cfg   = wc.get('classes', {}).get(cls, {})
    main_rule = get_rule(cls_cfg.get('main_rule_id', ''))
    return render_template('home_learning.html',
        cls=cls, class_options=CLASS_OPTIONS,
        week_ref=week_ref,
        main_rule_title=main_rule[2] if main_rule else '— (set in Settings)')


@hl_bp.route('/api/hl/ping')
def api_hl_ping():
    if not session.get('authenticated'):
        return jsonify({'ok': False}), 401
    errors = []
    try:
        import hl_generator
    except Exception as e:
        errors.append(f'hl_generator: {e}')
    try:
        import pdf_builder
    except Exception as e:
        errors.append(f'pdf_builder: {e}')
    try:
        import anthropic
        anthropic.Anthropic()
    except Exception as e:
        errors.append(f'anthropic: {e}')
    return jsonify({'ok': len(errors) == 0, 'errors': errors})


@hl_bp.route('/api/hl/generate', methods=['POST'])
def api_hl_generate():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401

    body             = request.get_json(force=True)
    cls              = body.get('cls', 'Y4_IM')
    maths_topic      = body.get('maths_topic', '').strip()
    maths_notes      = body.get('maths_notes', '').strip()
    reading_topic    = body.get('reading_topic', '').strip()
    vocab_word       = body.get('vocab_word', '').strip()
    rule_explanation = body.get('rule_explanation', '').strip()

    if not maths_topic or not reading_topic:
        return jsonify({'ok': False, 'error': 'Maths topic and reading text are required'})

    data = load_class(cls)
    if not data:
        return jsonify({'ok': False, 'error': f'Could not load class {cls}'})

    wc         = load_weekly_config()
    week_ref   = wc.get('week_ref', 'TxWy')
    cls_cfg    = wc.get('classes', {}).get(cls, {})
    main_rule  = get_rule(cls_cfg.get('main_rule_id', ''))
    rule_title = main_rule[2] if main_rule else ''
    rule_words = main_rule[3] if main_rule else []

    pupils     = data.get('pupils', [])
    std_pupils = _get_hl_pupils(pupils, 'standard')
    adp_pupils = _get_hl_pupils(pupils, 'adapted')

    key_words_map = {}
    for p in pupils:
        mastered = set(p.get('mastered', []))
        key_words_map[p['id']] = get_active_words(p.get('word_pos', 0), mastered, 5)

    is_column = _is_column_topic(maths_topic, maths_notes)

    try:
        from hl_generator import generate_hl_content
        std_data = generate_hl_content(
            maths_topic=maths_topic, reading_topic=reading_topic,
            week_ref=week_ref, version='standard',
            maths_notes=maths_notes, vocab_word=vocab_word)
        if is_column:
            std_data = _enforce_column_method(std_data)
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Standard content generation failed: {e}'})

    try:
        adp_data = generate_hl_content(
            maths_topic=maths_topic, reading_topic=reading_topic,
            week_ref=week_ref, version='adapted',
            maths_notes=maths_notes, vocab_word=vocab_word)
        if is_column:
            adp_data = _enforce_column_method(adp_data)
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Adapted content generation failed: {e}'})

    hl_cfg   = {'standard': std_data, 'adapted': adp_data}
    wkly_cfg = {'week_ref': week_ref}

    try:
        from pdf_builder import build_hl_pdf
        std_bytes = build_hl_pdf(
            std_pupils, hl_cfg, wkly_cfg, version='standard',
            rule_title=rule_title, rule_words=rule_words,
            key_words_map=key_words_map, rule_explanation=rule_explanation)
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Standard PDF build failed: {e}'})

    adp_bytes = None
    if adp_pupils:
        try:
            adp_bytes = build_hl_pdf(
                adp_pupils, hl_cfg, wkly_cfg, version='adapted',
                rule_title=rule_title, rule_words=rule_words,
                key_words_map=key_words_map, rule_explanation=rule_explanation)
        except Exception as e:
            return jsonify({'ok': False, 'error': f'Adapted PDF build failed: {e}'})

    return jsonify({
        'ok':      True,
        'week_ref': week_ref,
        'std_pdf': base64.b64encode(std_bytes).decode() if std_bytes else None,
        'adp_pdf': base64.b64encode(adp_bytes).decode() if adp_bytes else None,
        'n_std':   len(std_pupils),
        'n_adp':   len(adp_pupils),
    })

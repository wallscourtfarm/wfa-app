from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
import io, base64, traceback
from data_manager import load_class, load_weekly_config, get_rule, ALL_CLASSES, get_class_options, get_class_options_for_year, get_ref_class
from word_bank import get_active_words

print_bp = Blueprint('print_tools', __name__)

CLASS_OPTIONS = get_class_options()
DEFAULT_CLASS = 'all'


def _auth():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))


def _load_pupils(cls):
    if cls == 'all':
        pupils = []
        for cid in ALL_CLASSES:
            d = load_class(cid)
            if d:
                pupils.extend(d.get('pupils', []))
        return pupils
    d = load_class(cls)
    return d.get('pupils', []) if d else []


def _get_rules(cls):
    wc      = load_weekly_config()
    ref_cls = get_ref_class(cls)
    cfg     = wc.get('classes', {}).get(ref_cls, {})
    main    = get_rule(cfg.get('main_rule_id', ''))
    rev     = get_rule(cfg.get('revision_rule_id', ''))
    return main, rev, wc.get('week_ref', 'TxWy')


def _build_key_words_map(pupils):
    km = {}
    for p in pupils:
        mastered = set(p.get('mastered', []))
        km[p['id']] = get_active_words(p.get('word_pos', 0), mastered, 5)
    return km


def _err(e):
    return jsonify({'ok': False, 'error': str(e), 'detail': traceback.format_exc()})


# ── Page ──────────────────────────────────────────────────────────────────────

@print_bp.route('/print')
def print_page():
    r = _auth()
    if r: return r
    yr  = session.get('year_group', '4')
    cls = request.args.get('cls', f'Y{yr}_all')
    if cls not in [c[0] for c in get_class_options_for_year(session.get('year_group','4'))]:
        cls = DEFAULT_CLASS
    try:
        main_rule, rev_rule, week_ref = _get_rules(cls)
    except Exception:
        main_rule = rev_rule = None
        week_ref = '—'
    return render_template('print_tools.html',
        cls=cls,
        class_options=get_class_options_for_year(session.get("year_group","4")),
        week_ref=week_ref,
        main_rule_title=main_rule[2] if main_rule else '—',
        rev_rule_title=rev_rule[2]   if rev_rule  else '—',
    )


# ── API: Handwriting sheet ────────────────────────────────────────────────────

@print_bp.route('/api/print/handwriting', methods=['POST'])
def api_handwriting():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body = request.get_json(force=True)
        cls  = body.get('cls', DEFAULT_CLASS)
        main_rule, _, week_ref = _get_rules(cls)
        custom_raw = body.get('words', '').strip()
        if custom_raw:
            words = [w.strip() for w in custom_raw.replace(',', '\n').splitlines() if w.strip()]
        else:
            words = list(main_rule[3]) if main_rule else []
        if not words:
            return jsonify({'ok': False, 'error': 'No words — set a main rule in Settings or enter words manually'})
        from pdf_builder import build_handwriting_sheet
        data = build_handwriting_sheet(words, week_ref)
        return jsonify({
            'ok': True, 'data': base64.b64encode(data).decode(),
            'mime': 'application/pdf',
            'filename': f'Handwriting_{week_ref}.pdf',
            'n': len(words),
        })
    except Exception as e:
        return _err(e)


# ── API: Paired word lists ─────────────────────────────────────────────────────

@print_bp.route('/api/print/paired-lists', methods=['POST'])
def api_paired_lists():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        cls = request.get_json(force=True).get('cls', DEFAULT_CLASS)
        pupils = _load_pupils(cls)
        if not pupils:
            return jsonify({'ok': False, 'error': 'No pupils found'})
        main_rule, rev_rule, week_ref = _get_rules(cls)
        main_words    = list(main_rule[3]) if main_rule else []
        rev_words     = list(rev_rule[3])  if rev_rule  else []
        key_words_map = _build_key_words_map(pupils)
        from pdf_builder import build_paired_word_lists
        data = build_paired_word_lists(pupils, main_words, rev_words, key_words_map, week_ref)
        return jsonify({
            'ok': True, 'data': base64.b64encode(data).decode(),
            'mime': 'application/pdf',
            'filename': f'Paired_Lists_{week_ref}_{cls}.pdf',
            'n': len(pupils),
        })
    except Exception as e:
        return _err(e)


# ── API: Recording sheet ───────────────────────────────────────────────────────

@print_bp.route('/api/print/recording-sheet', methods=['POST'])
def api_recording_sheet():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        cls = request.get_json(force=True).get('cls', DEFAULT_CLASS)
        pupils = _load_pupils(cls)
        if not pupils:
            return jsonify({'ok': False, 'error': 'No pupils found'})
        _, _, week_ref = _get_rules(cls)
        from pdf_builder import build_recording_sheet
        data = build_recording_sheet(pupils, week_ref)
        return jsonify({
            'ok': True, 'data': base64.b64encode(data).decode(),
            'mime': 'application/pdf',
            'filename': f'Recording_Sheet_{week_ref}_{cls}.pdf',
            'n': len(pupils),
        })
    except Exception as e:
        return _err(e)


# ── API: TT check sheet ────────────────────────────────────────────────────────

@print_bp.route('/api/print/tt-check', methods=['POST'])
def api_tt_check():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        cls = request.get_json(force=True).get('cls', DEFAULT_CLASS)
        pupils = _load_pupils(cls)
        if not pupils:
            return jsonify({'ok': False, 'error': 'No pupils found'})
        _, _, week_ref = _get_rules(cls)
        from pdf_builder import build_tt_check_sheet
        data = build_tt_check_sheet(pupils, week_ref, seed=None)
        return jsonify({
            'ok': True, 'data': base64.b64encode(data).decode(),
            'mime': 'application/pdf',
            'filename': f'TT_Check_{week_ref}_{cls}.pdf',
            'n': len(pupils),
        })
    except Exception as e:
        return _err(e)

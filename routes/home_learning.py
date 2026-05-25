import base64
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import load_class, load_weekly_config, get_rule, ALL_CLASSES, get_class_options, get_class_options_for_year, get_ref_class
from word_bank import get_active_words

hl_bp = Blueprint('hl', __name__)
CLASS_OPTIONS = get_class_options()

# ── Async job store (disk-based — survives worker restarts) ─────────────────
import threading, uuid, time as _time, json as _json, os as _os

_JOB_DIR = '/tmp/hl_jobs'
_os.makedirs(_JOB_DIR, exist_ok=True)

def _job_path(job_id):
    return _os.path.join(_JOB_DIR, f'{job_id}.json')

def _job_write(job_id, data):
    data['ts'] = _time.time()
    try:
        with open(_job_path(job_id), 'w') as f:
            _json.dump(data, f)
    except Exception:
        pass

def _job_read(job_id):
    try:
        with open(_job_path(job_id)) as f:
            return _json.load(f)
    except Exception:
        return None

def _prune_jobs():
    """Remove job files older than 30 minutes."""
    cutoff = _time.time() - 1800
    try:
        for fn in _os.listdir(_JOB_DIR):
            fp = _os.path.join(_JOB_DIR, fn)
            if _os.path.getmtime(fp) < cutoff:
                _os.unlink(fp)
    except Exception:
        pass

COLUMN_KEYWORDS = {'column method', 'written method', 'written addition', 'written subtraction', 'formal written'}


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
    # Only check maths_topic — maths_notes are free-form teacher instructions
    # and should not trigger forced column method behaviour
    t = maths_topic.lower()
    return any(kw in t for kw in COLUMN_KEYWORDS)


def _load_class_pupils(cls):
    """Load pupils for one class, a year _all aggregate, or all classes combined."""
    from data_manager import _resolve_classes
    pupils = []
    for cid in _resolve_classes(cls):
        d = load_class(cid)
        if d:
            pupils.extend(d.get('pupils', []))
    return pupils


@hl_bp.route('/home-learning')
def home_learning():
    from flask import redirect
    return redirect('https://spelling-homelearning.streamlit.app/')


@hl_bp.route('/api/hl/ping')
def api_hl_ping():
    if not session.get('authenticated'):
        return jsonify({'ok': False}), 401
    errors = []
    for mod, obj in [('hl_generator', None), ('pdf_builder', None)]:
        try: __import__(mod)
        except Exception as e: errors.append(f'{mod}: {e}')
    try:
        import anthropic; anthropic.Anthropic()
    except Exception as e:
        errors.append(f'anthropic: {e}')
    return jsonify({'ok': len(errors) == 0, 'errors': errors})


@hl_bp.route('/api/hl/status/<job_id>')
def api_hl_status(job_id):
    """Poll job status — returns immediately."""
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    _prune_jobs()
    job = _job_read(job_id)
    if not job:
        return jsonify({'ok': False, 'status': 'error', 'error': 'Job not found or expired — please generate again'})
    return jsonify(job)


@hl_bp.route('/api/hl/generate', methods=['POST'])
def api_hl_generate():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    body = request.get_json(force=True)
    if not body:
        return jsonify({'ok': False, 'error': 'Invalid or empty request body'})
    cls = body.get('cls', 'all')
    maths_topic      = body.get('maths_topic', '').strip()
    maths_notes      = body.get('maths_notes', '').strip()
    reading_topic    = body.get('reading_topic', '').strip()
    vocab_word       = body.get('vocab_word', '').strip()
    rule_explanation = body.get('rule_explanation', '').strip()

    if not maths_topic or not reading_topic:
        return jsonify({'ok': False, 'error': 'Maths topic and reading text are required'})

    wc         = load_weekly_config() or {}
    week_ref   = wc.get('week_ref', 'TxWy')
    ref_cls    = get_ref_class(cls)
    cls_cfg    = wc.get('classes', {}).get(ref_cls, {})
    main_rule  = get_rule(cls_cfg.get('main_rule_id', ''))
    rule_title = main_rule[2] if main_rule else ''
    rule_words = main_rule[3] if main_rule else []

    pupils     = _load_class_pupils(cls)
    if not pupils:
        return jsonify({'ok': False, 'error': f'No pupils found for class {cls}'})

    std_pupils = _get_hl_pupils(pupils, 'standard')
    adp_pupils = _get_hl_pupils(pupils, 'adapted')

    key_words_map = {}
    for p in pupils:
        mastered = set(p.get('mastered', []))
        key_words_map[p['id']] = get_active_words(p.get('word_pos', 0), mastered, 5)

    is_column = _is_column_topic(maths_topic, maths_notes)

    job_id = str(uuid.uuid4())
    _job_write(job_id, {'status': 'pending'})

    # Capture everything needed for the thread (no request context in thread)
    _cls             = cls
    _maths_topic     = maths_topic
    _maths_notes     = maths_notes
    _reading_topic   = reading_topic
    _vocab_word      = vocab_word
    _rule_explanation= rule_explanation
    _week_ref        = week_ref
    _rule_title      = rule_title
    _rule_words      = rule_words
    _std_pupils      = std_pupils
    _adp_pupils      = adp_pupils
    _key_words_map   = key_words_map
    _is_col          = is_column

    def _run():
        from hl_generator import generate_hl_content

        # Run standard and adapted content generation in parallel
        results = {}
        errors  = {}

        def _gen(version):
            try:
                data = generate_hl_content(
                    maths_topic=_maths_topic, reading_topic=_reading_topic,
                    week_ref=_week_ref, version=version,
                    maths_notes=_maths_notes, vocab_word=_vocab_word)
                if _is_col:
                    data = _enforce_column_method(data)
                results[version] = data
            except Exception as e:
                errors[version] = str(e)

        t_std = threading.Thread(target=_gen, args=('standard',), daemon=True)
        t_adp = threading.Thread(target=_gen, args=('adapted',),  daemon=True)
        t_std.start(); t_adp.start()
        t_std.join();  t_adp.join()

        if 'standard' in errors:
            _job_write(job_id, {'status': 'error', 'error': f'Standard content failed: {errors["standard"]}'})
            return

        std_data = results.get('standard')
        adp_data = results.get('adapted')

        hl_cfg   = {'standard': std_data, 'adapted': adp_data}
        wkly_cfg = {'week_ref': _week_ref}

        from pdf_builder import build_hl_pdf
        _pdfs = {}

        def _build_pdf(ver, pupils):
            try:
                _pdfs[ver] = build_hl_pdf(
                    pupils, hl_cfg, wkly_cfg, version=ver,
                    rule_title=_rule_title, rule_words=_rule_words,
                    key_words_map=_key_words_map, rule_explanation=_rule_explanation)
            except Exception as e:
                _pdfs[ver + '_err'] = str(e)

        tp1 = threading.Thread(target=_build_pdf, args=('standard', _std_pupils), daemon=True)
        tp2 = threading.Thread(target=_build_pdf, args=('adapted', _adp_pupils), daemon=True) if _adp_pupils else None
        tp1.start()
        if tp2: tp2.start()
        tp1.join()
        if tp2: tp2.join()

        if 'standard_err' in _pdfs:
            _job_write(job_id, {'status': 'error', 'error': f'Standard PDF failed: {_pdfs["standard_err"]}'})            
            return

        std_bytes = _pdfs.get('standard')
        adp_bytes = _pdfs.get('adapted')

        _job_write(job_id, {
            'status':   'done',
            'ok':       True,
            'week_ref': _week_ref,
            'std_pdf':  base64.b64encode(std_bytes).decode() if std_bytes else None,
            'adp_pdf':  base64.b64encode(adp_bytes).decode() if adp_bytes else None,
            'n_std':    len(_std_pupils),
            'n_adp':    len(_adp_pupils),
        })

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'ok': True, 'job_id': job_id, 'status': 'pending'})

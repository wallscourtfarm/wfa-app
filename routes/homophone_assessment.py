import os, base64, json, traceback, uuid, re
from datetime import date
import requests as _req
from flask import (Blueprint, render_template, request, jsonify,
                   session, redirect, url_for, Response, stream_with_context)
from data_manager import load_class, load_weekly_config, ALL_CLASSES, get_class_options, get_ref_class
from spelling_rules import SPELLING_RULES

ha_bp = Blueprint('homophone_assessment', __name__)

CLASS_OPTIONS = get_class_options()
DEFAULT_CLASS  = 'all'

PAT       = os.environ.get('GITHUB_TOKEN', '')
DATA_REPO = os.environ.get('DATA_REPO', 'wallscourtfarm/spelling-homelearning')
_HDR      = {'Authorization': f'token {PAT}', 'Accept': 'application/vnd.github.v3+json'}
ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages'

# Confidence thresholds
CONFIDENT  = 0.90
PARTIAL    = 0.60

# Stage → year label
STAGE_YEARS = {2: 'approx. Y2', 3: 'approx. Y3', 4: 'approx. Y4', 5: 'approx. Y5'}


def _auth():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))

def _err(e):
    return jsonify({'ok': False, 'error': str(e), 'detail': traceback.format_exc()})

def _load_pupils(cls):
    if cls == 'all':
        pupils = []
        for cid in ALL_CLASSES:
            d = load_class(cid)
            if d: pupils.extend(d.get('pupils', []))
        return pupils
    d = load_class(cls)
    return d.get('pupils', []) if d else []

def _load_rule_cloze():
    r = _req.get(
        f'https://api.github.com/repos/{DATA_REPO}/contents/data/rule_cloze_sentences.json',
        headers=_HDR, timeout=10)
    if r.status_code == 200:
        return json.loads(base64.b64decode(r.json()['content']).decode())
    return {}

def _homophone_rules_by_stage():
    """
    Returns {stage: [(rule_id, title, [words])]} for all homophone rules,
    sorted by step within each stage.
    """
    result = {}
    for r in SPELLING_RULES:
        stage, step, title, words, rtype = r
        if 'homophone' not in title.lower() and 'near-homophone' not in title.lower():
            continue
        if rtype != 0:  # skip challenge and revision
            continue
        rid = f'{stage}-{step}'
        result.setdefault(stage, []).append((rid, title, words))
    return {s: sorted(rules, key=lambda x: int(x[0].split('-')[1]))
            for s, rules in result.items()}

def _build_sections(selected_stages, cloze_bank):
    """
    Returns list of (stage, stage_label, [(rule_id, word, sentence)...])
    for all words in selected stages — ALL words per rule, not just 2.
    """
    rules_by_stage = _homophone_rules_by_stage()
    sections = []
    for stage in sorted(selected_stages):
        rules = rules_by_stage.get(stage, [])
        stage_label = f'Stage {stage} ({STAGE_YEARS.get(stage, "")})'
        rows = []
        for rule_id, title, words in rules:
            cloze_entry = cloze_bank.get(rule_id, {})
            sents = {s['word'].lower(): s['sentence']
                     for s in cloze_entry.get('sentences', [])}
            for word in words:
                sentence = sents.get(word.lower(),
                                     f'Write the word: {"_" * 35}.')
                sentence = re.sub(r'_+', '_' * 35, sentence)
                rows.append((rule_id, word, sentence))
        if rows:
            sections.append((stage, stage_label, rows))
    return sections

def _word_list_text(sections):
    lines, words = [], []
    n = 1
    for stage, label, rows in sections:
        for rule_id, word, _ in rows:
            lines.append(f'{n}. {word} ({rule_id})')
            words.append((n, word, rule_id))
            n += 1
    return words, '\n'.join(lines)

def _vision_prompt(word_list_text):
    return (
        "This is a scanned page from a homophone assessment for Year 3/4 pupils.\n\n"
        "The child's name is pre-printed at the top — read it exactly as printed.\n\n"
        "The assessment tests homophones in context (cloze sentences). "
        "Each row has a small square box on the right. "
        "The teacher marks correct answers by drawing a single diagonal line "
        "corner to corner across the box. "
        "An empty box or a stray mark (not a full diagonal) means incorrect.\n\n"
        f"Words being tested on this page:\n{word_list_text}\n\n"
        'Return ONLY valid JSON: {"name": "Full Name", "results": {"word1": true, "word2": false}}\n'
        "true = diagonal line, false = empty. Omit words not on this page. "
        "No preamble, no markdown fences."
    )

def _stage_summary(homophone_mastered, sections):
    """Compute per-stage confidence from mastered set."""
    summary = {}
    mastered = {w.lower() for w in homophone_mastered}
    for stage, label, rows in sections:
        stage_words = {word.lower() for _, word, _ in rows}
        correct = len(mastered & stage_words)
        total   = len(stage_words)
        pct     = correct / total if total else 0
        status  = ('confident' if pct >= CONFIDENT
                   else 'partial' if pct >= PARTIAL
                   else 'developing')
        summary[stage] = {'correct': correct, 'total': total,
                          'pct': round(pct, 3), 'status': status}
    return summary


# ── Page ──────────────────────────────────────────────────────────────────────

@ha_bp.route('/homophone-assessment')
def homophone_assessment():
    r = _auth()
    if r: return r
    cls = request.args.get('cls', DEFAULT_CLASS)
    if cls not in [c[0] for c in CLASS_OPTIONS]:
        cls = DEFAULT_CLASS
    wc       = load_weekly_config()
    week_ref = wc.get('week_ref', 'TxWy')
    rules_by_stage = _homophone_rules_by_stage()
    stage_info = {
        stage: {
            'label':  f'Stage {stage} ({STAGE_YEARS.get(stage, "")})',
            'n_rules': len(rules),
            'n_words': sum(len(r[2]) for r in rules),
        }
        for stage, rules in sorted(rules_by_stage.items())
    }
    return render_template('homophone_assessment.html',
        cls=cls, class_options=CLASS_OPTIONS,
        week_ref=week_ref, stage_info=stage_info)


# ── Generate ──────────────────────────────────────────────────────────────────

@ha_bp.route('/api/homophone-assessment/generate', methods=['POST'])
def api_ha_generate():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body           = request.get_json(force=True)
        cls            = body.get('cls', DEFAULT_CLASS)
        selected       = [int(s) for s in body.get('stages', [])]
        if not selected:
            return jsonify({'ok': False, 'error': 'Select at least one stage'})

        pupils   = _load_pupils(cls)
        if not pupils:
            return jsonify({'ok': False, 'error': 'No pupils found'})

        wc       = load_weekly_config()
        week_ref = wc.get('week_ref', 'TxWy')
        cloze    = _load_rule_cloze()
        sections = _build_sections(selected, cloze)

        from assessment_builder import build_homophone_assessment_pdf, build_homophone_assessment_teacher_pdf
        pdf_bytes     = build_homophone_assessment_pdf(pupils, sections, week_ref)
        teacher_bytes = build_homophone_assessment_teacher_pdf(sections, week_ref)

        n_words = sum(len(rows) for _, _, rows in sections)
        return jsonify({
            'ok':               True,
            'pdf':              base64.b64encode(pdf_bytes).decode(),
            'teacher_pdf':      base64.b64encode(teacher_bytes).decode(),
            'pdf_name':         f'Homophone_Assessment_{week_ref}_{cls}_Pupils.pdf',
            'teacher_pdf_name': f'Homophone_Assessment_{week_ref}_Teacher.pdf',
            'n_pupils': len(pupils), 'n_words': n_words,
        })
    except Exception as e:
        return _err(e)


# ── Upload (step 1) ───────────────────────────────────────────────────────────

@ha_bp.route('/api/homophone-assessment/import-upload', methods=['POST'])
def api_ha_import_upload():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body    = request.get_json(force=True)
        pdf_b64 = body.get('pdf', '')
        if not pdf_b64:
            return jsonify({'ok': False, 'error': 'No PDF provided'})

        pdf_bytes = base64.b64decode(pdf_b64)
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        n_pages = len(doc); doc.close()

        job_id = str(uuid.uuid4())
        with open(f'/tmp/ha_{job_id}.pdf', 'wb') as f: f.write(pdf_bytes)
        with open(f'/tmp/ha_{job_id}.json', 'w') as f:
            json.dump({'cls': body.get('cls', DEFAULT_CLASS),
                       'stages': body.get('stages', []),
                       'n_pages': n_pages}, f)

        # Compute total words for correct denominator on frontend
        cloze    = _load_rule_cloze()
        sections = _build_sections(selected, cloze)
        total_words = sum(len(rows) for _, _, rows in sections)
        return jsonify({'ok': True, 'job_id': job_id, 'n_pages': n_pages,
                        'total_words': total_words})
    except Exception as e:
        return _err(e)


# ── Stream (step 2) ───────────────────────────────────────────────────────────

@ha_bp.route('/api/homophone-assessment/import-stream/<job_id>')
def api_ha_import_stream(job_id):
    try: uuid.UUID(job_id)
    except ValueError:
        return jsonify({'ok': False, 'error': 'Invalid job ID'}), 400

    tmp_pdf  = f'/tmp/ha_{job_id}.pdf'
    tmp_meta = f'/tmp/ha_{job_id}.json'
    if not os.path.exists(tmp_pdf):
        return jsonify({'ok': False, 'error': 'Job not found — re-upload'}), 404

    with open(tmp_meta) as f: meta = json.load(f)
    selected = [int(s) for s in meta['stages']]
    cloze    = _load_rule_cloze()
    sections = _build_sections(selected, cloze)
    _, wl_text = _word_list_text(sections)
    prompt   = _vision_prompt(wl_text)
    api_key  = os.environ.get('ANTHROPIC_API_KEY', '')

    def sse(data): return f"data: {json.dumps(data)}\n\n"

    def generate():
        import fitz
        try:
            with open(tmp_pdf, 'rb') as f: pdf_bytes = f.read()
            doc = fitz.open(stream=pdf_bytes, filetype='pdf')
            n_pages = len(doc)

            for page_num in range(n_pages):
                yield ": keepalive\n\n"
                try:
                    mat = fitz.Matrix(200/72, 200/72)
                    pix = doc[page_num].get_pixmap(matrix=mat)
                    img_b64 = base64.b64encode(pix.tobytes('png')).decode()

                    resp = _req.post(ANTHROPIC_URL,
                        headers={'x-api-key': api_key,
                                 'anthropic-version': '2023-06-01',
                                 'content-type': 'application/json'},
                        json={'model': 'claude-sonnet-4-20250514', 'max_tokens': 1500,
                              'messages': [{'role': 'user', 'content': [
                                  {'type': 'image', 'source': {
                                      'type': 'base64', 'media_type': 'image/png', 'data': img_b64}},
                                  {'type': 'text', 'text': prompt}]}]},
                        timeout=45)

                    if resp.status_code == 200:
                        text = resp.json()['content'][0]['text'].strip()
                        text = re.sub(r'^```[a-z]*\n?', '', text)
                        text = re.sub(r'\n?```$', '', text)
                        parsed = json.loads(text)
                        yield sse({'type': 'page', 'page_num': page_num + 1,
                                   'total': n_pages, 'name': parsed.get('name', ''),
                                   'results': parsed.get('results', {})})
                    else:
                        yield sse({'type': 'error', 'page_num': page_num + 1,
                                   'total': n_pages, 'message': f'API {resp.status_code}'})
                except Exception as e:
                    yield sse({'type': 'error', 'page_num': page_num + 1,
                               'total': n_pages, 'message': str(e)})

            doc.close()
            yield sse({'type': 'done', 'total': n_pages})
        except Exception as e:
            yield sse({'type': 'fatal', 'message': str(e)})
        finally:
            for f in [tmp_pdf, tmp_meta]:
                try: os.remove(f)
                except OSError: pass

    return Response(stream_with_context(generate()), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


# ── Confirm ───────────────────────────────────────────────────────────────────

@ha_bp.route('/api/homophone-assessment/confirm', methods=['POST'])
def api_ha_confirm():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body          = request.get_json(force=True)
        cls           = body.get('cls', DEFAULT_CLASS)
        selected      = [int(s) for s in body.get('stages', [])]
        week_ref      = body.get('week_ref', '')
        pupil_results = body.get('results', {})  # {name_lower: {name, results: {word: bool}}}

        cloze    = _load_rule_cloze()
        sections = _build_sections(selected, cloze)
        today    = date.today().strftime('%Y-%m-%d')

        class_ids = ALL_CLASSES if cls == 'all' else [cls]
        saved, unmatched = 0, []

        for cid in class_ids:
            r2 = _req.get(
                f'https://api.github.com/repos/{DATA_REPO}/contents/data/classes/{cid}.json',
                headers=_HDR, timeout=10)
            if r2.status_code != 200: continue
            file_data = r2.json()
            sha       = file_data['sha']
            class_obj = json.loads(base64.b64decode(file_data['content']).decode())
            changed   = False

            for p in class_obj.get('pupils', []):
                name_key = (p.get('first','') + ' ' + (p.get('last') or '')).strip().lower()
                if name_key not in pupil_results:
                    unmatched.append((p.get('first','') + ' ' + (p.get('last') or '')).strip())
                    continue

                # Initialise all assessment words as False (incorrect),
                # then overlay what Vision returned. Ensures denominator = all words.
                all_words = {word.lower(): False
                             for _, _, rows in sections
                             for _, word, _ in rows}
                for k, v in pupil_results[name_key]['results'].items():
                    if k.lower() in all_words:
                        all_words[k.lower()] = v

                hm = set(p.get('homophone_mastered', []))
                for w, correct in all_words.items():
                    if correct:
                        hm.add(w)
                    else:
                        hm.discard(w)

                p['homophone_mastered'] = sorted(hm)

                # Store stage summaries for quick display
                p.setdefault('homophone_history', {})
                for stage, stage_label, rows in sections:
                    stage_words = {word.lower() for _, word, _ in rows}
                    correct_ct  = len(hm & stage_words)
                    total_ct    = len(stage_words)
                    pct         = round(correct_ct / total_ct, 3) if total_ct else 0
                    status      = ('confident' if pct >= CONFIDENT
                                   else 'partial' if pct >= PARTIAL else 'developing')
                    p['homophone_history'].setdefault(str(stage), []).append({
                        'week': week_ref, 'date': today,
                        'correct': correct_ct, 'total': total_ct,
                        'score': pct, 'status': status,
                    })

                saved += 1; changed = True

            if changed:
                content = base64.b64encode(
                    json.dumps(class_obj, indent=2, ensure_ascii=False).encode()).decode()
                _req.put(
                    f'https://api.github.com/repos/{DATA_REPO}/contents/data/classes/{cid}.json',
                    headers=_HDR,
                    json={'message': 'Homophone Assessment import', 'content': content,
                          'sha': sha, 'branch': 'main'}, timeout=15)

        return jsonify({'ok': True, 'saved': saved, 'unmatched': unmatched})
    except Exception as e:
        return _err(e)

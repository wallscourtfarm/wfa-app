import os, io, base64, json, traceback, uuid, re
import requests as _req
from flask import (Blueprint, render_template, request, jsonify,
                   session, redirect, url_for, Response, stream_with_context)
from data_manager import load_class, load_weekly_config, ALL_CLASSES, get_class_options, get_ref_class

wa_bp = Blueprint('word_assessment', __name__)

CLASS_OPTIONS = get_class_options()
DEFAULT_CLASS = 'all'
SECTION_KEYS  = ['Y1/Y2', 'Y3', 'Y4']

PAT       = os.environ.get('GITHUB_TOKEN', '')
DATA_REPO = os.environ.get('DATA_REPO', 'wallscourtfarm/spelling-homelearning')
_HDR      = {'Authorization': f'token {PAT}', 'Accept': 'application/vnd.github.v3+json'}

ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages'


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
            if d:
                pupils.extend(d.get('pupils', []))
        return pupils
    d = load_class(cls)
    return d.get('pupils', []) if d else []

def _load_cloze_bank():
    r = _req.get(
        f'https://api.github.com/repos/{DATA_REPO}/contents/data/cloze_sentences.json',
        headers=_HDR, timeout=10)
    if r.status_code == 200:
        raw = base64.b64decode(r.json()['content']).decode()
        return {e['word'].lower(): e['sentence'] for e in json.loads(raw)}
    return {}

def _sections_from_keys(selected):
    from assessment_builder import _all_sections
    all_sec = _all_sections()
    return [(all_sec[k][0], all_sec[k][1]) for k in selected if k in all_sec]

def _word_list_text(sections):
    words = [w for _, ws in sections for w in ws]
    return words, "\n".join(f"{i+1}. {w}" for i, w in enumerate(words))

def _vision_prompt(word_list_text):
    return (
        "This is a scanned page from a Year 3/4 spelling assessment completed by a primary school pupil.\n\n"
        "The child's name is pre-printed at the top of the page — read it exactly as printed.\n\n"
        f"The assessment tests these words in order:\n{word_list_text}\n\n"
        "Each row has a small square box on the right-hand side. The teacher marks correct answers "
        "by drawing a single diagonal line from one corner of the box to the opposite corner. "
        "An empty box or a box with only a small stray mark (not a full diagonal) means incorrect.\n\n"
        "For each word that appears on this page, return true if the box contains a corner-to-corner "
        "diagonal line, false if it is empty or has only a stray mark.\n\n"
        "Return ONLY valid JSON: {\"name\": \"Full Name\", \"results\": {\"word1\": true, \"word2\": false}}\n"
        "true = diagonal line present, false = empty or stray mark. "
        "Omit words not on this page. No preamble, no markdown fences."
    )


# ── Page ──────────────────────────────────────────────────────────────────────

@wa_bp.route('/word-assessment')
def word_assessment():
    r = _auth()
    if r: return r
    cls = request.args.get('cls', DEFAULT_CLASS)
    if cls not in [c[0] for c in CLASS_OPTIONS]:
        cls = DEFAULT_CLASS
    wc       = load_weekly_config()
    week_ref = wc.get('week_ref', 'TxWy')
    return render_template('word_assessment.html',
        cls=cls, class_options=CLASS_OPTIONS,
        week_ref=week_ref, section_keys=SECTION_KEYS)


# ── API: Generate sheets ───────────────────────────────────────────────────────

@wa_bp.route('/api/word-assessment/generate', methods=['POST'])
def api_wa_generate():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body     = request.get_json(force=True)
        cls      = body.get('cls', DEFAULT_CLASS)
        selected = body.get('sections', SECTION_KEYS)

        pupils   = _load_pupils(cls)
        if not pupils:
            return jsonify({'ok': False, 'error': 'No pupils found'})

        wc       = load_weekly_config()
        week_ref = wc.get('week_ref', 'TxWy')
        cloze    = _load_cloze_bank()
        sections = _sections_from_keys(selected)
        all_words = [w for _, ws in sections for w in ws]

        missing = [w for w in all_words if w.lower() not in cloze]
        if missing:
            from assessment_builder import generate_missing_cloze
            api_key = os.environ.get('ANTHROPIC_API_KEY', '')
            if api_key:
                cloze.update(generate_missing_cloze(missing, api_key))

        from assessment_builder import build_word_assessment_pdf, build_word_assessment_excel, build_word_assessment_teacher_pdf
        pdf_bytes     = build_word_assessment_pdf(pupils, sections, cloze, week_ref)
        teacher_bytes = build_word_assessment_teacher_pdf([], sections, cloze, week_ref)
        xl_bytes      = build_word_assessment_excel(pupils, sections)

        flagged = [w for w in missing if w.lower() not in cloze]
        return jsonify({
            'ok':           True,
            'pdf':          base64.b64encode(pdf_bytes).decode(),
            'teacher_pdf':  base64.b64encode(teacher_bytes).decode(),
            'excel':        base64.b64encode(xl_bytes).decode(),
            'pdf_name':          f'Word_Assessment_{week_ref}_{cls}_Pupils.pdf',
            'teacher_pdf_name':  f'Word_Assessment_{week_ref}_{cls}_Teacher.pdf',
            'excel_name':        f'Word_Assessment_{week_ref}_{cls}_Marking.xlsx',
            'n_pupils':  len(pupils),
            'n_words':   len(all_words),
            'flagged':   flagged,
        })
    except Exception as e:
        return _err(e)


# ── API: Upload PDF (step 1 of streaming import) ──────────────────────────────

@wa_bp.route('/api/word-assessment/import-upload', methods=['POST'])
def api_wa_import_upload():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body    = request.get_json(force=True)
        pdf_b64 = body.get('pdf', '')
        if not pdf_b64:
            return jsonify({'ok': False, 'error': 'No PDF provided'})

        pdf_bytes = base64.b64decode(pdf_b64)

        import fitz
        doc     = fitz.open(stream=pdf_bytes, filetype='pdf')
        n_pages = len(doc)
        doc.close()

        job_id = str(uuid.uuid4())
        with open(f'/tmp/wa_{job_id}.pdf', 'wb') as f:
            f.write(pdf_bytes)
        with open(f'/tmp/wa_{job_id}.json', 'w') as f:
            json.dump({
                'cls':      body.get('cls', DEFAULT_CLASS),
                'sections': body.get('sections', SECTION_KEYS),
                'n_pages':  n_pages,
            }, f)

        cloze_tmp    = _load_cloze_bank()
        secs_tmp     = _sections_from_keys(body.get('sections', SECTION_KEYS))
        total_words  = sum(len(ws) for _, ws in secs_tmp)
        return jsonify({'ok': True, 'job_id': job_id, 'n_pages': n_pages,
                        'total_words': total_words})
    except Exception as e:
        return _err(e)


# ── API: Stream processing (step 2) ───────────────────────────────────────────

@wa_bp.route('/api/word-assessment/import-stream/<job_id>')
def api_wa_import_stream(job_id):
    # Basic validation — job_id must be a UUID
    try:
        uuid.UUID(job_id)
    except ValueError:
        return jsonify({'ok': False, 'error': 'Invalid job ID'}), 400

    tmp_pdf  = f'/tmp/wa_{job_id}.pdf'
    tmp_meta = f'/tmp/wa_{job_id}.json'

    if not os.path.exists(tmp_pdf):
        return jsonify({'ok': False, 'error': 'Job not found — re-upload the PDF'}), 404

    with open(tmp_meta) as f:
        meta = json.load(f)

    sections      = _sections_from_keys(meta['sections'])
    _, wl_text    = _word_list_text(sections)
    prompt        = _vision_prompt(wl_text)
    api_key       = os.environ.get('ANTHROPIC_API_KEY', '')

    def sse(data):
        return f"data: {json.dumps(data)}\n\n"

    def generate():
        import fitz

        try:
            with open(tmp_pdf, 'rb') as f:
                pdf_bytes = f.read()

            doc     = fitz.open(stream=pdf_bytes, filetype='pdf')
            n_pages = len(doc)

            for page_num in range(n_pages):
                # Keepalive comment so proxies don't drop idle connection
                yield ": keepalive\n\n"

                try:
                    page      = doc[page_num]
                    mat       = fitz.Matrix(200/72, 200/72)
                    pix       = page.get_pixmap(matrix=mat)
                    img_b64   = base64.b64encode(pix.tobytes('png')).decode()

                    resp = _req.post(
                        ANTHROPIC_URL,
                        headers={'x-api-key': api_key,
                                 'anthropic-version': '2023-06-01',
                                 'content-type': 'application/json'},
                        json={
                            'model':      'claude-sonnet-4-20250514',
                            'max_tokens': 1000,
                            'messages': [{'role': 'user', 'content': [
                                {'type': 'image', 'source': {
                                    'type': 'base64',
                                    'media_type': 'image/png',
                                    'data': img_b64}},
                                {'type': 'text', 'text': prompt},
                            ]}],
                        },
                        timeout=45,
                    )

                    if resp.status_code == 200:
                        text = resp.json()['content'][0]['text'].strip()
                        text = re.sub(r'^```[a-z]*\n?', '', text)
                        text = re.sub(r'\n?```$', '', text)
                        parsed = json.loads(text)
                        yield sse({
                            'type':     'page',
                            'page_num': page_num + 1,
                            'total':    n_pages,
                            'name':     parsed.get('name', ''),
                            'results':  parsed.get('results', {}),
                        })
                    else:
                        yield sse({
                            'type':     'error',
                            'page_num': page_num + 1,
                            'total':    n_pages,
                            'message':  f'API error {resp.status_code}',
                        })

                except Exception as e:
                    yield sse({
                        'type':     'error',
                        'page_num': page_num + 1,
                        'total':    n_pages,
                        'message':  str(e),
                    })

            doc.close()
            yield sse({'type': 'done', 'total': n_pages})

        except Exception as e:
            yield sse({'type': 'fatal', 'message': str(e)})
        finally:
            for f in [tmp_pdf, tmp_meta]:
                try:
                    os.remove(f)
                except OSError:
                    pass

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control':    'no-cache',
            'X-Accel-Buffering': 'no',   # prevent nginx buffering
        },
    )


# ── API: Confirm — write results to class data ────────────────────────────────

@wa_bp.route('/api/word-assessment/confirm', methods=['POST'])
def api_wa_confirm():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body    = request.get_json(force=True)
        cls     = body.get('cls', DEFAULT_CLASS)
        # results: {name_lower: {name, results: {word: bool}}}
        results = body.get('results', {})

        from word_bank import WORD_BANK
        class_ids = ALL_CLASSES if cls == 'all' else [cls]
        saved = 0
        unmatched = []

        for cid in class_ids:
            r2 = _req.get(
                f'https://api.github.com/repos/{DATA_REPO}/contents/data/classes/{cid}.json',
                headers=_HDR, timeout=10)
            if r2.status_code != 200:
                continue
            file_data = r2.json()
            sha       = file_data['sha']
            class_obj = json.loads(base64.b64decode(file_data['content']).decode())
            pupils    = class_obj.get('pupils', [])
            changed   = False

            for p in pupils:
                name_key = (p.get('first','') + ' ' + (p.get('last') or '')).strip().lower()
                if name_key not in results:
                    unmatched.append((p.get('first','') + ' ' + (p.get('last') or '')).strip())
                    continue

                # Initialise all assessment words as False, overlay Vision results
                all_words = {word.lower(): False
                             for _, words in sections for word in words}
                for k, v in results[name_key]['results'].items():
                    if k.lower() in all_words:
                        all_words[k.lower()] = v

                mastered = set(p.get('mastered', []))
                for word, correct in all_words.items():
                    if correct:
                        mastered.add(word)
                    else:
                        mastered.discard(word)
                p['mastered'] = sorted(mastered)
                for wi, (w, *_) in enumerate(WORD_BANK):
                    if w not in mastered:
                        p['word_pos'] = wi
                        break
                else:
                    p['word_pos'] = len(WORD_BANK)
                saved   += 1
                changed  = True

            if changed:
                content = base64.b64encode(
                    json.dumps(class_obj, indent=2, ensure_ascii=False).encode()).decode()
                _req.put(
                    f'https://api.github.com/repos/{DATA_REPO}/contents/data/classes/{cid}.json',
                    headers=_HDR,
                    json={'message': 'Word Assessment import', 'content': content,
                          'sha': sha, 'branch': 'main'},
                    timeout=15)

        return jsonify({'ok': True, 'saved': saved, 'unmatched': unmatched})
    except Exception as e:
        return _err(e)

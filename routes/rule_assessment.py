import os, io, base64, json, traceback, uuid, re, unicodedata
from datetime import date
import requests as _req
from flask import (Blueprint, render_template, request, jsonify,
                   session, redirect, url_for, Response, stream_with_context)
from data_manager import load_class, load_weekly_config, ALL_CLASSES, get_class_options, get_class_options_for_year, get_ref_class, _resolve_classes
from uls_lessons import ULS_LESSONS

ra_bp = Blueprint('rule_assessment', __name__)

CLASS_OPTIONS = get_class_options()
DEFAULT_CLASS = 'all'

PAT       = os.environ.get('GITHUB_TOKEN', '')
DATA_REPO = os.environ.get('DATA_REPO', 'wallscourtfarm/spelling-homelearning')
_HDR      = {'Authorization': f'token {PAT}', 'Accept': 'application/vnd.github.v3+json'}
ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages'

WORDS_PER_LESSON = 2   # always test first 2 words from each lesson's cloze bank


def _auth():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))

def _err(e):
    return jsonify({'ok': False, 'error': str(e), 'detail': traceback.format_exc()})

def _norm_name(s):
    """Normalise a name for fuzzy matching: lowercase, strip hyphens/punctuation, collapse spaces."""
    s = unicodedata.normalize('NFC', s or '')
    s = re.sub(r"[-–—_']", ' ', s)          # hyphens/dashes/apostrophes → space
    s = re.sub(r'[^a-z0-9 ]', '', s.lower()) # strip anything else
    return re.sub(r' +', ' ', s).strip()

def _load_pupils(cls):
    pupils = []
    for cid in _resolve_classes(cls):
        d = load_class(cid)
        if d: pupils.extend(d.get('pupils', []))
    return pupils

def _load_rule_cloze():
    r = _req.get(
        f'https://api.github.com/repos/{DATA_REPO}/contents/data/uls_cloze_sentences.json',
        headers=_HDR, timeout=10)
    if r.status_code == 200:
        return json.loads(base64.b64decode(r.json()['content']).decode())
    return {}

def _plannable_lessons():
    """Returns ULS lessons for Y3-Y6 (Y2 excluded — word/focus alignment not yet verified)."""
    return [l for l in ULS_LESSONS if l['year'] != 'Y2']

def _rule_sections(selected_ids, cloze_bank):
    """
    Build list of (lesson_id, title, [(word, sentence), (word, sentence)])
    for the selected lesson IDs. Uses first WORDS_PER_LESSON sentences from the bank.
    """
    sections = []
    for lesson_id in selected_ids:
        entry = cloze_bank.get(lesson_id)
        if not entry:
            continue
        sentences = entry.get('sentences', [])[:WORDS_PER_LESSON]
        if not sentences:
            continue
        pairs = [(s['word'], s['sentence']) for s in sentences]
        sections.append((lesson_id, entry['title'], pairs))
    return sections

def _vision_prompt(sections):
    """Build a prompt that tells Claude the lesson→word mapping on this page."""
    lines = []
    for lesson_id, title, pairs in sections:
        words = ' and '.join(f'"{w}"' for w, _ in pairs)
        lines.append(f'  Lesson {lesson_id} ({title}): tests {words}')
    lesson_map = '\n'.join(lines)

    return (
        "This is a scanned page from a ULS spelling assessment.\n\n"
        "The child's name is pre-printed at the top of the page — read it exactly as printed.\n\n"
        "The assessment is grouped by spelling lesson. Each lesson has exactly 2 words tested. "
        "The lessons and their words on this page are:\n"
        f"{lesson_map}\n\n"
        "Each row has a small square box on the right-hand side. The teacher marks correct answers "
        "by drawing a single diagonal line from one corner of the box to the opposite corner. "
        "An empty box or a box with only a small stray mark means incorrect.\n\n"
        "Return ONLY valid JSON:\n"
        '{"name": "Full Name", "results": {"word1": true, "word2": false, ...}}\n'
        "true = diagonal line present, false = empty or stray mark. "
        "Omit words not visible on this page. No preamble, no markdown fences."
    )


# ── Page ──────────────────────────────────────────────────────────────────────

@ra_bp.route('/rule-reassessment')
def rule_reassessment():
    r = _auth()
    if r: return r
    yr  = session.get('year_group', '4')
    cls = request.args.get('cls', f'Y{yr}_all')
    if cls not in [c[0] for c in get_class_options_for_year(session.get('year_group','4'))]:
        cls = DEFAULT_CLASS
    wc       = load_weekly_config()
    week_ref = wc.get('week_ref', 'TxWy')
    lessons  = _plannable_lessons()

    # Group by year → term → week for the selector
    uls_years = {}
    for l in lessons:
        uls_years.setdefault(l['year'], {}) \
                 .setdefault(l['term'], {}) \
                 .setdefault(l['week'], []) \
                 .append({'id': l['id'], 'focus': l['focus'],
                          'sequence': l.get('sequence',''), 'lesson': l.get('lesson','')})

    return render_template('rule_assessment.html',
        cls=cls, class_options=get_class_options_for_year(session.get("year_group","4")),
        week_ref=week_ref, uls_years=uls_years, active_year=yr)


# ── API: Generate sheets ───────────────────────────────────────────────────────

@ra_bp.route('/api/rule-assessment/generate', methods=['POST'])
def api_ra_generate():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body         = request.get_json(force=True)
        cls          = body.get('cls', DEFAULT_CLASS)
        selected_ids = body.get('rules', [])

        if not selected_ids:
            return jsonify({'ok': False, 'error': 'Select at least one rule'})

        pupils    = _load_pupils(cls)
        if not pupils:
            return jsonify({'ok': False, 'error': 'No pupils found'})

        wc        = load_weekly_config()
        week_ref  = wc.get('week_ref', 'TxWy')
        cloze     = _load_rule_cloze()
        sections  = _rule_sections(selected_ids, cloze)

        if not sections:
            return jsonify({'ok': False, 'error': 'No cloze sentences found for selected rules'})

        from assessment_builder import build_rule_assessment_pdf, build_rule_assessment_teacher_pdf
        pdf_bytes     = build_rule_assessment_pdf(pupils, sections, week_ref)
        teacher_bytes = build_rule_assessment_teacher_pdf([], sections, week_ref)

        return jsonify({
            'ok':          True,
            'pdf':         base64.b64encode(pdf_bytes).decode(),
            'teacher_pdf': base64.b64encode(teacher_bytes).decode(),
            'pdf_name':         f'Rule_Assessment_{week_ref}_{cls}_Pupils.pdf',
            'teacher_pdf_name': f'Rule_Assessment_{week_ref}_{cls}_Teacher.pdf',
            'n_pupils':  len(pupils),
            'n_rules':   len(sections),
            'n_words':   len(sections) * WORDS_PER_LESSON,
        })
    except Exception as e:
        return _err(e)


# ── API: Upload (step 1) ───────────────────────────────────────────────────────

@ra_bp.route('/api/rule-assessment/import-upload', methods=['POST'])
def api_ra_import_upload():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body         = request.get_json(force=True)
        pdf_b64      = body.get('pdf', '')
        selected_ids = body.get('rules', [])

        if not pdf_b64:
            return jsonify({'ok': False, 'error': 'No PDF provided'})

        pdf_bytes = base64.b64decode(pdf_b64)
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        n_pages = len(doc)
        doc.close()

        job_id = str(uuid.uuid4())
        with open(f'/tmp/ra_{job_id}.pdf', 'wb') as f:
            f.write(pdf_bytes)
        with open(f'/tmp/ra_{job_id}.json', 'w') as f:
            json.dump({'cls': body.get('cls', DEFAULT_CLASS),
                       'rules': selected_ids, 'n_pages': n_pages}, f)

        cloze_tmp   = _load_rule_cloze()
        secs_tmp    = _rule_sections(body.get('rules', []), cloze_tmp)
        total_words = len(secs_tmp) * WORDS_PER_LESSON
        return jsonify({'ok': True, 'job_id': job_id, 'n_pages': n_pages,
                        'total_words': total_words})
    except Exception as e:
        return _err(e)


# ── API: Stream (step 2) ───────────────────────────────────────────────────────

@ra_bp.route('/api/rule-assessment/import-stream/<job_id>')
def api_ra_import_stream(job_id):
    try:
        uuid.UUID(job_id)
    except ValueError:
        return jsonify({'ok': False, 'error': 'Invalid job ID'}), 400

    tmp_pdf  = f'/tmp/ra_{job_id}.pdf'
    tmp_meta = f'/tmp/ra_{job_id}.json'

    if not os.path.exists(tmp_pdf):
        return jsonify({'ok': False, 'error': 'Job not found — re-upload the PDF'}), 404

    with open(tmp_meta) as f:
        meta = json.load(f)

    cloze    = _load_rule_cloze()
    sections = _rule_sections(meta['rules'], cloze)
    prompt   = _vision_prompt(sections)
    api_key  = os.environ.get('ANTHROPIC_API_KEY', '')

    def sse(data):
        return f"data: {json.dumps(data)}\n\n"

    def _process_page(args):
        """Process a single page: render + Claude Vision. Returns (page_num, result_dict)."""
        import fitz as _fitz
        page_num, pdf_bytes_inner = args
        try:
            doc_inner = _fitz.open(stream=pdf_bytes_inner, filetype='pdf')
            page      = doc_inner[page_num]
            mat       = _fitz.Matrix(150/72, 150/72)   # 150 DPI — faster, still readable
            pix       = page.get_pixmap(matrix=mat)
            img_b64   = base64.b64encode(pix.tobytes('png')).decode()
            doc_inner.close()

            resp = _req.post(
                ANTHROPIC_URL,
                headers={'x-api-key': api_key,
                         'anthropic-version': '2023-06-01',
                         'content-type': 'application/json'},
                json={'model': 'claude-sonnet-4-5', 'max_tokens': 1000,
                      'messages': [{'role': 'user', 'content': [
                          {'type': 'image', 'source': {
                              'type': 'base64', 'media_type': 'image/png', 'data': img_b64}},
                          {'type': 'text', 'text': prompt},
                      ]}]},
                timeout=45,
            )
            if resp.status_code == 200:
                text   = resp.json()['content'][0]['text'].strip()
                text   = re.sub(r'^```[a-z]*\n?', '', text)
                text   = re.sub(r'\n?```$', '', text)
                parsed = json.loads(text)
                return (page_num, {'type': 'page',
                                   'name': parsed.get('name', ''),
                                   'results': parsed.get('results', {})})
            else:
                return (page_num, {'type': 'error',
                                   'message': f'API {resp.status_code}'})
        except Exception as e:
            return (page_num, {'type': 'error', 'message': str(e)})

    def generate():
        import fitz
        from concurrent.futures import ThreadPoolExecutor, as_completed
        try:
            with open(tmp_pdf, 'rb') as f:
                pdf_bytes = f.read()

            doc     = fitz.open(stream=pdf_bytes, filetype='pdf')
            n_pages = len(doc)
            doc.close()

            yield sse({'type': 'total', 'total': n_pages})

            BATCH = 5  # concurrent API calls
            for batch_start in range(0, n_pages, BATCH):
                yield ": keepalive\n\n"
                batch = list(range(batch_start, min(batch_start + BATCH, n_pages)))
                futures = {}
                with ThreadPoolExecutor(max_workers=BATCH) as ex:
                    for pn in batch:
                        futures[ex.submit(_process_page, (pn, pdf_bytes))] = pn
                    for fut in as_completed(futures):
                        page_num, result = fut.result()
                        result['page_num'] = page_num + 1
                        result['total']    = n_pages
                        yield sse(result)

            yield sse({'type': 'done', 'total': n_pages})

        except Exception as e:
            yield sse({'type': 'fatal', 'message': str(e)})
        finally:
            for f in [tmp_pdf, tmp_meta]:
                try: os.remove(f)
                except OSError: pass

    return Response(stream_with_context(generate()),
                    mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


# ── API: Confirm ───────────────────────────────────────────────────────────────

@ra_bp.route('/api/rule-assessment/confirm', methods=['POST'])
def api_ra_confirm():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body         = request.get_json(force=True)
        cls          = body.get('cls', DEFAULT_CLASS)
        selected_ids = body.get('rules', [])
        week_ref     = body.get('week_ref', '')
        # pupil_results: {name_lower: {name, results: {word: bool}}}
        # Normalise keys so hyphens/punctuation variations still match
        raw_results   = body.get('results', {})
        pupil_results = {_norm_name(k): v for k, v in raw_results.items()}

        cloze    = _load_rule_cloze()
        sections = _rule_sections(selected_ids, cloze)

        # Build word → rule_id map
        word_to_rule = {}
        for rule_id, title, pairs in sections:
            for word, _ in pairs:
                word_to_rule[word.lower()] = (rule_id, title)

        today     = date.today().strftime('%Y-%m-%d')
        class_ids = _resolve_classes(cls)
        saved     = 0
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
                name_key = _norm_name(p.get('first','') + ' ' + (p.get('last') or ''))
                if name_key not in pupil_results:
                    unmatched.append((p.get('first','') + ' ' + (p.get('last') or '')).strip())
                    continue

                word_results = pupil_results[name_key]['results']  # {word: bool}
                rc = dict(p.get('rule_confidence', {}))

                # Score each rule: tally the 2 tested words
                for rule_id, title, pairs in sections:
                    # All words for this rule default to False; overlay Vision results
                    all_rule = {word.lower(): False for word, _ in pairs}
                    for k, v in word_results.items():
                        if k.lower() in all_rule:
                            all_rule[k.lower()] = v
                    tested  = list(all_rule.items())
                    correct = sum(1 for _, v in tested if v)
                    total   = len(tested)
                    # Status
                    if correct == total:
                        status = 'full'
                    elif correct > 0:
                        status = 'partial'
                    else:
                        status = 'none'

                    rc.setdefault(rule_id, []).append({
                        'week':    week_ref,
                        'rule':    title,
                        'date':    today,
                        'status':  status,
                        'correct': correct,
                        'total':   total,
                        'score':   round(correct / total, 4) if total else 0,
                    })

                p['rule_confidence'] = rc
                saved   += 1
                changed  = True

            if changed:
                content = base64.b64encode(
                    json.dumps(class_obj, indent=2, ensure_ascii=False).encode()).decode()
                put_r = _req.put(
                    f'https://api.github.com/repos/{DATA_REPO}/contents/data/classes/{cid}.json',
                    headers=_HDR,
                    json={'message': 'Rule Assessment import', 'content': content,
                          'sha': sha, 'branch': 'main'},
                    timeout=15)
                if put_r.status_code not in (200, 201):
                    return jsonify({'ok': False,
                                    'error': f'GitHub save failed for {cid}: {put_r.status_code} {put_r.text[:200]}'}), 500

        return jsonify({'ok': True, 'saved': saved, 'unmatched': unmatched})
    except Exception as e:
        return _err(e)

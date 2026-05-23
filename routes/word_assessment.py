import os, io, base64, json, traceback
import requests as _req
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for

from data_manager import load_class, load_weekly_config, ALL_CLASSES

wa_bp = Blueprint('word_assessment', __name__)

CLASS_OPTIONS = [('all', 'Y4 ALL'), ('Y4_IM', 'Y4 IM'), ('Y4_WU', 'Y4 WU')]
DEFAULT_CLASS = 'all'
SECTION_KEYS  = ['Y1/Y2', 'Y3', 'Y4']

PAT     = os.environ.get('GITHUB_TOKEN', '')
DATA_REPO = os.environ.get('DATA_REPO', 'wallscourtfarm/spelling-homelearning')
_HDR    = {'Authorization': f'token {PAT}', 'Accept': 'application/vnd.github.v3+json'}


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
        entries = json.loads(raw)
        return {e['word'].lower(): e['sentence'] for e in entries}
    return {}


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
        selected = body.get('sections', SECTION_KEYS)   # list of section keys

        pupils   = _load_pupils(cls)
        if not pupils:
            return jsonify({'ok': False, 'error': 'No pupils found'})

        wc       = load_weekly_config()
        week_ref = wc.get('week_ref', 'TxWy')

        cloze    = _load_cloze_bank()

        from assessment_builder import _all_sections, generate_missing_cloze
        all_sec  = _all_sections()
        sections = [(all_sec[k][0], all_sec[k][1]) for k in selected if k in all_sec]

        # Check for missing cloze entries
        all_words = [w for _, words in sections for w in words]
        missing   = [w for w in all_words if w.lower() not in cloze]
        if missing:
            api_key = os.environ.get('ANTHROPIC_API_KEY', '')
            if api_key:
                generated = generate_missing_cloze(missing, api_key)
                cloze.update(generated)
            # Anything still missing falls back to plain "Write the word: ___"

        from assessment_builder import build_word_assessment_pdf, build_word_assessment_excel
        pdf_bytes = build_word_assessment_pdf(pupils, sections, cloze, week_ref)
        xl_bytes  = build_word_assessment_excel(pupils, sections)

        flagged = [w for w in missing if w.lower() not in cloze]

        return jsonify({
            'ok':      True,
            'pdf':     base64.b64encode(pdf_bytes).decode(),
            'excel':   base64.b64encode(xl_bytes).decode(),
            'pdf_name':   f'Word_Assessment_{week_ref}_{cls}_Pupils.pdf',
            'excel_name': f'Word_Assessment_{week_ref}_{cls}_Marking.xlsx',
            'n_pupils':   len(pupils),
            'n_words':    len(all_words),
            'flagged':    flagged,   # words that had no cloze and couldn't be generated
        })
    except Exception as e:
        return _err(e)


# ── API: Import scanned PDF ────────────────────────────────────────────────────

@wa_bp.route('/api/word-assessment/import', methods=['POST'])
def api_wa_import():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body     = request.get_json(force=True)
        cls      = body.get('cls', DEFAULT_CLASS)
        selected = body.get('sections', SECTION_KEYS)
        pdf_b64  = body.get('pdf', '')

        if not pdf_b64:
            return jsonify({'ok': False, 'error': 'No PDF provided'})

        pdf_bytes = base64.b64decode(pdf_b64)

        from assessment_builder import _all_sections
        all_sec   = _all_sections()
        sections  = [(all_sec[k][0], all_sec[k][1]) for k in selected if k in all_sec]
        all_words = [w for _, words in sections for w in words]
        word_list_text = "\n".join(f"{i+1}. {w}" for i, w in enumerate(all_words))

        # Convert PDF pages to images using PyMuPDF
        import fitz   # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            return jsonify({'ok': False, 'error': 'ANTHROPIC_API_KEY not set'})

        # Process each page — collect results by pupil name
        pupil_pages = {}   # name_lower -> list of page result dicts

        for page_num in range(len(doc)):
            page = doc[page_num]
            # Render at 200 DPI
            mat  = fitz.Matrix(200/72, 200/72)
            pix  = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            img_b64   = base64.b64encode(img_bytes).decode()

            prompt = (
                f"This is a scanned page from a Year 3/4 spelling assessment completed by a primary school pupil.\n\n"
                f"The child's name is pre-printed at the top of the page — read it exactly as printed.\n\n"
                f"The assessment tests these words in order:\n{word_list_text}\n\n"
                f"Each row has a small square box on the right-hand side. The teacher has marked each box "
                f"to indicate correct (tick, filled box, circle, dot, or any mark inside the box) "
                f"or left it empty to indicate incorrect.\n\n"
                f"For each word that appears on this page, return whether the box is marked (correct=true) "
                f"or empty (correct=false).\n\n"
                f"Return ONLY valid JSON with this structure:\n"
                f'{{"name": "Full Name", "results": {{"word1": true, "word2": false, ...}}}}\n'
                f"true = box marked, false = box empty, omit words not visible on this page.\n"
                f"No preamble, no markdown fences."
            )

            resp = _req.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": [
                        {"type": "image", "source": {
                            "type": "base64", "media_type": "image/png", "data": img_b64}},
                        {"type": "text", "text": prompt}
                    ]}]
                },
                timeout=45,
            )

            if resp.status_code != 200:
                continue

            text = resp.json()["content"][0]["text"].strip()
            text = __import__('re').sub(r"^```[a-z]*\n?", "", text)
            text = __import__('re').sub(r"\n?```$", "", text)

            try:
                page_data = json.loads(text)
                name_key  = page_data.get("name", "").strip().lower()
                results   = page_data.get("results", {})
                if name_key:
                    if name_key not in pupil_pages:
                        pupil_pages[name_key] = {"name": page_data["name"], "results": {}}
                    pupil_pages[name_key]["results"].update(results)
            except Exception:
                pass   # unparseable page — skip

        doc.close()

        # Build summary for confirmation step
        summary = []
        for name_key, data in pupil_pages.items():
            res     = data["results"]
            correct = sum(1 for v in res.values() if v)
            total   = len(res)
            summary.append({
                "name":    data["name"],
                "correct": correct,
                "total":   total,
                "results": res,
            })

        # Store in session for confirm step
        session['wa_import'] = {
            'cls': cls, 'selected': selected,
            'pupil_results': {d['name'].lower(): d for d in summary}
        }

        return jsonify({'ok': True, 'summary': summary, 'n_pages': len(doc) if False else len(pupil_pages)})

    except Exception as e:
        return _err(e)


# ── API: Confirm import (write to class data) ──────────────────────────────────

@wa_bp.route('/api/word-assessment/confirm', methods=['POST'])
def api_wa_confirm():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        import_data = session.get('wa_import')
        if not import_data:
            return jsonify({'ok': False, 'error': 'No pending import — please re-scan'})

        cls     = import_data['cls']
        results = import_data['pupil_results']   # name_lower -> {name, results}

        from data_manager import load_class, ALL_CLASSES
        from word_bank import WORD_BANK
        import requests as rq

        def _save_class(class_id, data, sha):
            content = base64.b64encode(
                json.dumps(data, indent=2, ensure_ascii=False).encode()).decode()
            rq.put(
                f'https://api.github.com/repos/{DATA_REPO}/contents/data/classes/{class_id}.json',
                headers=_HDR,
                json={'message': 'Word Assessment import', 'content': content,
                      'sha': sha, 'branch': 'main'},
                timeout=15)

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
                    unmatched.append(p.get('first','') + ' ' + (p.get('last') or ''))
                    continue
                res = results[name_key]['results']
                mastered = set(p.get('mastered', []))
                for word, correct in res.items():
                    if correct:
                        mastered.add(word)
                    else:
                        mastered.discard(word)
                p['mastered'] = sorted(mastered)
                # Recalculate word_pos
                for wi, (w, *_) in enumerate(WORD_BANK):
                    if w not in mastered:
                        p['word_pos'] = wi
                        break
                else:
                    p['word_pos'] = len(WORD_BANK)
                saved  += 1
                changed = True

            if changed:
                _save_class(cid, class_obj, sha)

        session.pop('wa_import', None)
        return jsonify({'ok': True, 'saved': saved, 'unmatched': unmatched})

    except Exception as e:
        return _err(e)

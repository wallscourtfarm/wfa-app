import os, json, base64, uuid
from datetime import datetime, date
import requests as _req
from flask import (Blueprint, render_template, request, jsonify,
                   session, redirect, url_for, send_file, make_response)
from data_manager import load_class, load_weekly_config, ALL_CLASSES, get_class_options, get_class_options_for_year, get_ref_class, _resolve_classes
from word_bank import WORD_BANK
from spelling_rules import SPELLING_RULES

live_bp = Blueprint('live', __name__)

PAT       = os.environ.get('GITHUB_TOKEN', '')
DATA_REPO = os.environ.get('DATA_REPO', 'wallscourtfarm/spelling-homelearning')
_HDR      = {'Authorization': f'token {PAT}', 'Accept': 'application/vnd.github.v3+json'}

WB = [w[0] for w in WORD_BANK]

CLASS_OPTIONS = get_class_options()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _auth():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))

def _err(e):
    import traceback
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

def _pupil_active_words(p, n=5):
    pos = p.get('word_pos', 0)
    return WB[pos:pos + n]

def _rule_words(wc, cls):
    """Get up to 5 rule words for the current week from weekly config."""
    from data_manager import get_ref_class as _grc, get_rule
    cfg  = wc.get('classes', {}).get(_grc(cls), {})
    words = []
    for key in ('main_rule_id', 'revision_rule_id'):
        rid = cfg.get(key, '')
        if rid:
            rule = get_rule(rid)
            if rule: words.extend(rule[3])
    return list(dict.fromkeys(words))[:5]   # dedupe, max 5

def _save_session(session_id, data):
    path    = f'data/sessions/{session_id}.json'
    content = base64.b64encode(json.dumps(data, indent=2).encode()).decode()
    r = _req.put(
        f'https://api.github.com/repos/{DATA_REPO}/contents/{path}',
        headers=_HDR,
        json={'message': f'Create session {session_id}', 'content': content, 'branch': 'main'},
        timeout=15)
    return r.status_code in (200, 201)

def _load_session(session_id):
    r = _req.get(
        f'https://api.github.com/repos/{DATA_REPO}/contents/data/sessions/{session_id}.json',
        headers=_HDR, timeout=10)
    if r.status_code == 200:
        return json.loads(base64.b64decode(r.json()['content']).decode())
    return None

def _save_result(session_id, pupil_id, data):
    path    = f'data/results/{session_id}_{pupil_id}.json'
    content = base64.b64encode(json.dumps(data, indent=2).encode()).decode()
    r = _req.put(
        f'https://api.github.com/repos/{DATA_REPO}/contents/{path}',
        headers=_HDR,
        json={'message': f'Result {session_id} {pupil_id}',
              'content': content, 'branch': 'main'},
        timeout=15)
    return r.status_code in (200, 201)

def _load_results(session_id):
    """Load all result files for a session."""
    r = _req.get(
        f'https://api.github.com/repos/{DATA_REPO}/contents/data/results',
        headers=_HDR, timeout=10)
    if r.status_code != 200:
        return []
    results = []
    for f in r.json():
        if f['name'].startswith(f'{session_id}_') and f['name'].endswith('.json'):
            r2 = _req.get(f['download_url'], timeout=10)
            if r2.status_code == 200:
                results.append(r2.json())
    return results


# ── Teacher: Spelling Bee session creation ────────────────────────────────────

@live_bp.route('/live/bee')
def bee_sessions():
    """Redirect to spelling bee page — session creation is now there."""
    return redirect(url_for('bee.spelling_bee'))


@live_bp.route('/api/live/bee/create', methods=['POST'])
def api_bee_create():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body     = request.get_json(force=True)
        cls      = body.get('cls', 'all')
        wc       = load_weekly_config()
        week_ref = wc.get('week_ref', '')
        rule_wds = _rule_words(wc, cls)

        class_ids = _resolve_classes(cls)
        all_pupils = {}
        for cid in class_ids:
            d = load_class(cid)
            if d:
                for p in d.get('pupils', []):
                    all_pupils[p['id']] = p

        session_id   = uuid.uuid4().hex[:8].upper()
        session_data = {
            'session_id': session_id,
            'created_at': datetime.now().isoformat(),
            'week_ref':   week_ref,
            'type':       'spelling_bee',
            'items':      [],
            'pupils': []
        }

        for pid, p in all_pupils.items():
            partner = all_pupils.get(p.get('pair_id', ''), {})
            key_wds = _pupil_active_words(p, 5)
            all_wds = key_wds + rule_wds
            session_data['pupils'].append({
                'id':           pid,
                'first':        p.get('first', ''),
                'last':         p.get('last', ''),
                'cls':          p.get('cls', ''),
                'pair_colour':  p.get('pair_colour') or '#1798d3',
                'items':        [{'word': w} for w in all_wds],
                'partner_id':   partner.get('id', ''),
                'partner_name': partner.get('first', ''),
            })

        ok = _save_session(session_id, session_data)
        if not ok:
            return jsonify({'ok': False, 'error': 'Could not save session'})

        base_url  = request.host_url.rstrip('/')
        n_words   = 5 + len(rule_wds)

        return jsonify({
            'ok':         True,
            'session_id': session_id,
            'week_ref':   week_ref,
            'n_pupils':   len(session_data['pupils']),
            'n_words':    n_words,
            'base_url':   base_url,
        })
    except Exception as e:
        return _err(e)


@live_bp.route('/api/live/bee/cards-pdf/<session_id>')
def api_bee_cards_pdf(session_id):
    """Generate 6-up QR card PDF for a bee session."""
    r = _auth()
    if r: return r
    try:
        sess = _load_session(session_id)
        if not sess:
            return 'Session not found', 404

        base_url = request.host_url.rstrip('/')
        pdf_bytes = _build_bee_cards(sess, base_url)
        response  = make_response(pdf_bytes)
        response.headers['Content-Type']        = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=SpellingBee_{session_id}.pdf'
        return response
    except Exception as e:
        return str(e), 500


def _build_bee_cards(sess, base_url):
    """ReportLab 6-up (2×3) QR cards for spelling bee."""
    import io, qrcode
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader

    W, H     = A4
    M        = 6 * mm
    COLS, ROWS = 2, 3
    col_w    = (W - 2 * M) / COLS
    row_h    = (H - 2 * M) / ROWS
    NAVY     = (0.055, 0.157, 0.255)
    session_id = sess['session_id']
    week_ref   = sess.get('week_ref', '')

    def hex_to_rgb(h):
        h = h.lstrip('#')
        return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))

    buf = io.BytesIO()
    c   = rl_canvas.Canvas(buf, pagesize=A4)

    def draw_cut_lines():
        c.saveState()
        c.setStrokeColorRGB(0.65, 0.65, 0.65)
        c.setLineWidth(0.4)
        c.setDash([4, 3])
        for ci in range(COLS + 1):
            lx = M + ci * col_w
            c.line(lx, 0, lx, H)
        for ri in range(ROWS + 1):
            ly = H - M - ri * row_h
            c.line(0, ly, W, ly)
        c.restoreState()

    def draw_card(cx, cy, p_rec):
        """Draw one card at column-left cx, row-top cy."""
        PAD      = 5 * mm
        HDR_H    = 22 * mm
        words    = [it['word'] for it in p_rec.get('items', [])]
        n_wds    = len(words)
        colour_rgb = hex_to_rgb(p_rec.get('pair_colour') or '#1798d3')
        name       = f"{p_rec['first']} {p_rec.get('last', '')}".strip()
        partner    = p_rec.get('partner_name', '')

        # ── Colour header ────────────────────────────────────────────────────
        c.setFillColorRGB(*colour_rgb)
        c.rect(cx, cy - HDR_H, col_w, HDR_H, fill=1, stroke=0)

        # Name pill — use ReportLab's built-in roundRect
        pill_w = min(col_w - 8 * mm, len(name) * 7.5 + 16)
        pill_h = 10 * mm
        pill_x = cx + (col_w - pill_w) / 2
        pill_y = cy - HDR_H / 2 - pill_h / 2 + (3 * mm if partner else 0)
        c.setFillColorRGB(1, 1, 1)
        c.roundRect(pill_x, pill_y, pill_w, pill_h, 5, stroke=0, fill=1)
        c.setFillColorRGB(*NAVY)
        c.setFont('Helvetica-Bold', 14)
        c.drawCentredString(cx + col_w / 2, pill_y + 2.5 * mm, name)

        # Partner pill
        if partner:
            p_pill_w = min(col_w - 16 * mm, len(f'Partner: {partner}') * 5.2 + 14)
            p_pill_h = 6 * mm
            p_pill_x = cx + (col_w - p_pill_w) / 2
            p_pill_y = pill_y - p_pill_h - 2 * mm
            c.setFillColorRGB(1, 1, 1)
            c.roundRect(p_pill_x, p_pill_y, p_pill_w, p_pill_h, 3, stroke=0, fill=1)
            c.setFillColorRGB(*NAVY)
            c.setFont('Helvetica', 8)
            c.drawCentredString(cx + col_w / 2, p_pill_y + 1.5 * mm, f'Partner: {partner}')

        # ── QR code ───────────────────────────────────────────────────────────
        url     = f'{base_url}/live/bee/{session_id}/{p_rec["id"]}'
        qr      = qrcode.QRCode(box_size=5, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img     = qr.make_image(fill_color='#1a3c6e', back_color='white')
        qr_io   = __import__('io').BytesIO()
        img.save(qr_io, format='PNG')
        qr_io.seek(0)
        qr_size = 30 * mm
        qr_x    = cx + PAD
        qr_y    = cy - HDR_H - qr_size - 3 * mm
        c.drawImage(ImageReader(qr_io), qr_x, qr_y, qr_size, qr_size)

        # Session info beside QR
        info_x = qr_x + qr_size + 3 * mm
        c.setFont('Helvetica-Bold', 7)
        c.setFillColorRGB(*NAVY)
        c.drawString(info_x, qr_y + qr_size - 9, f'Session: {session_id}')
        if week_ref:
            c.setFont('Helvetica', 7)
            c.drawString(info_x, qr_y + qr_size - 18, week_ref)
        c.setFont('Helvetica', 6.5)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawString(info_x, qr_y + 4, 'Scan to start →')

        # ── Word list — 2 columns (key words left, rule words right) ─────────
        word_top  = qr_y - 3 * mm
        avail_h   = word_top - (cy - row_h + PAD)
        split     = 5                             # first 5 = key spellings
        n_left    = min(split, n_wds)
        n_right   = max(0, n_wds - split)
        n_rows    = max(n_left, n_right, 1)
        word_h    = min(5.5 * mm, avail_h / n_rows)
        fs        = 11
        half_w    = (col_w - 2 * PAD) / 2

        # Vertical centre-line divider when both columns are used
        if n_right > 0:
            mid_x = cx + PAD + half_w
            c.setStrokeColorRGB(0.80, 0.80, 0.80)
            c.setLineWidth(0.4)
            c.line(mid_x, word_top, mid_x, word_top - n_rows * word_h)

        for i, word in enumerate(words):
            col_x  = cx + PAD + (0 if i < split else half_w + 2 * mm)
            row_i  = i if i < split else i - split
            wy     = word_top - row_i * word_h
            c.setFont('Helvetica-Bold' if i < split else 'Helvetica', fs)
            c.setFillColorRGB(*(NAVY if i < split else (0.22, 0.22, 0.52)))
            c.drawString(col_x, wy, f'{i + 1}.  {word}')

    pupils = sess.get('pupils', [])
    for idx, p_rec in enumerate(pupils):
        slot = idx % (COLS * ROWS)
        if slot == 0 and idx > 0:
            draw_cut_lines()
            c.showPage()
        col  = slot % COLS
        row  = slot // COLS
        cx   = M + col * col_w
        cy   = H - M - row * row_h
        draw_card(cx, cy, p_rec)

    draw_cut_lines()
    c.save()
    buf.seek(0)
    return buf.read()


# ── Pupil: Spelling Bee page ──────────────────────────────────────────────────

@live_bp.route('/live/bee/<session_id>/<pupil_id>')
def bee_pupil(session_id, pupil_id):
    """Full-screen iPad spelling bee page — no auth required."""
    sess = _load_session(session_id)
    if not sess:
        return render_template('live_error.html', msg='Session not found. Ask your teacher.')
    pupil = next((p for p in sess.get('pupils', []) if p['id'] == pupil_id), None)
    if not pupil:
        return render_template('live_error.html', msg='Pupil not found in this session.')
    return render_template('live_bee_pupil.html',
        session_id=session_id,
        pupil=pupil,
        items=pupil.get('items', []),
        week_ref=sess.get('week_ref', ''))


# ── Pupil: Submit result ──────────────────────────────────────────────────────

def _typed_matches_word(typed, word):
    """Case-insensitive match; respect capitalisation for proper nouns."""
    t = typed.strip()
    if t.lower() != word.lower():
        return False
    if word[0] != word[0].lower():   # proper noun — must be capitalised
        return t[0] != t[0].lower()
    return True


@live_bp.route('/api/live/submit', methods=['POST'])
def api_live_submit():
    """Save pupil assessment result (called by JS on pupil's device).

    Scoring is set-based: a word is counted correct if it was typed correctly
    at ANY point in the session, not just in the matching slot.  This prevents
    a one-word-skipped read by the partner from wiping out the whole score.
    """
    try:
        body       = request.get_json(force=True)
        session_id = body.get('session_id', '')
        pupil_id   = body.get('pupil_id', '')
        answers    = body.get('answers', [])  # [{word, typed, correct}]
        sess_type  = body.get('session_type', 'spelling_bee')

        if not session_id or not pupil_id:
            return jsonify({'ok': False, 'error': 'Missing session_id or pupil_id'})

        # Load session to get the canonical word list for this pupil
        sess        = _load_session(session_id)
        typed_strs  = [a.get('typed', '') for a in answers]

        if sess:
            pupil_sess     = next((p for p in sess.get('pupils', []) if p['id'] == pupil_id), None)
            expected_words = [item['word'] for item in (pupil_sess or {}).get('items', [])]
        else:
            expected_words = [a['word'] for a in answers]

        # A word is correct if it was typed correctly at any point in the session
        correct_set = {w for w in expected_words
                       if any(_typed_matches_word(t, w) for t in typed_strs)}
        correct = len(correct_set)
        total   = len(expected_words) or len(answers)

        result = {
            'session_id':    session_id,
            'pupil_id':      pupil_id,
            'name':          body.get('name', ''),
            'week_ref':      body.get('week_ref', ''),
            'session_type':  sess_type,
            'submitted':     datetime.now().isoformat(),
            'correct':       correct,
            'total':         total,
            'score_pct':     round(correct / total * 100) if total else 0,
            'correct_words': sorted(correct_set),
            'answers':       answers,
        }
        ok = _save_result(session_id, pupil_id, result)
        return jsonify({'ok': ok, 'correct': correct, 'total': total,
                        'score_pct': result['score_pct']})
    except Exception as e:
        return _err(e)


# ── Teacher: View / process session results ───────────────────────────────────

@live_bp.route('/api/live/bee/process', methods=['POST'])
def api_bee_process():
    """Process spelling bee results → update mastered/word_pos per pupil."""
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body       = request.get_json(force=True)
        session_id = body.get('session_id', '')
        if not session_id:
            return jsonify({'ok': False, 'error': 'No session_id'})

        results = _load_results(session_id)
        if not results:
            return jsonify({'ok': False, 'error': 'No results found for this session'})

        # Load session to get pupil→word mapping
        sess = _load_session(session_id)
        if not sess:
            return jsonify({'ok': False, 'error': 'Session not found'})

        pupil_map = {p['id']: p for p in sess.get('pupils', [])}
        week_ref  = sess.get('week_ref', '')
        today     = date.today().strftime('%Y-%m-%d')

        # Group results by class
        class_updates = {}   # cid → {pid → result}
        for res in results:
            pid = res.get('pupil_id', '')
            if pid in pupil_map:
                class_updates.setdefault('', {})[pid] = res

        saved, skipped = 0, 0
        for cid in ALL_CLASSES:
            d = load_class(cid)
            if not d: continue
            r2 = _req.get(
                f'https://api.github.com/repos/{DATA_REPO}/contents/data/classes/{cid}.json',
                headers=_HDR, timeout=10)
            if r2.status_code != 200: continue
            file_data = r2.json()
            sha       = file_data['sha']
            class_obj = json.loads(base64.b64decode(file_data['content']).decode())
            changed   = False

            for p in class_obj.get('pupils', []):
                pid = p['id']
                res = next((r for r in results if r.get('pupil_id') == pid), None)
                if not res:
                    skipped += 1
                    continue

                sess_pupil = pupil_map.get(pid, {})
                items      = sess_pupil.get('items', [])
                answers    = res.get('answers', [])

                # Build word→correct lookup
                ans_map = {a['word'].lower(): a.get('correct', False) for a in answers}
                mastered = set(p.get('mastered', []))

                for item in items:
                    word = item['word']
                    if ans_map.get(word.lower(), False):
                        mastered.add(word)
                    # Don't remove from mastered — bee is low-stakes

                # Advance word_pos for words now mastered
                pos = p.get('word_pos', 0)
                while pos < len(WB) and WB[pos] in mastered:
                    pos += 1

                p['mastered']  = sorted(mastered)
                p['word_pos']  = pos
                saved  += 1
                changed = True

            if changed:
                content = base64.b64encode(
                    json.dumps(class_obj, indent=2, ensure_ascii=False).encode()).decode()
                _req.put(
                    f'https://api.github.com/repos/{DATA_REPO}/contents/data/classes/{cid}.json',
                    headers=_HDR,
                    json={'message': f'Spelling bee {session_id} import',
                          'content': content, 'sha': sha, 'branch': 'main'},
                    timeout=15)

        return jsonify({'ok': True, 'saved': saved, 'skipped': skipped,
                        'total_results': len(results)})
    except Exception as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED ASSESSMENT SESSIONS  (/live/assess/...)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_cloze_bank():
    r = _req.get(
        f'https://api.github.com/repos/{DATA_REPO}/contents/data/cloze_sentences.json',
        headers=_HDR, timeout=10)
    if r.status_code == 200:
        raw = base64.b64decode(r.json()['content']).decode()
        return {e['word'].lower(): e['sentence'] for e in json.loads(raw)}
    return {}

def _load_rule_cloze():
    r = _req.get(
        f'https://api.github.com/repos/{DATA_REPO}/contents/data/rule_cloze_sentences.json',
        headers=_HDR, timeout=10)
    if r.status_code == 200:
        return json.loads(base64.b64decode(r.json()['content']).decode())
    return {}

def _homophone_rules_by_stage():
    result = {}
    for r in SPELLING_RULES:
        stage, step, title, words, rtype = r
        if 'homophone' not in title.lower():
            continue
        if rtype != 0:
            continue
        rid = f'{stage}-{step}'
        result.setdefault(stage, []).append((rid, title, words))
    return result

def _build_assess_qr_pdf(session_id, url, week_ref, assessment_type, n_pupils, n_words):
    """A4 PDF suitable for projecting — shows URL + QR code prominently."""
    import io, qrcode
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader

    W, H   = A4
    NAVY   = (26/255, 60/255, 110/255)
    BLUE   = (23/255, 152/255, 211/255)

    buf = io.BytesIO()
    c   = rl_canvas.Canvas(buf, pagesize=A4)

    # Header bar
    c.setFillColorRGB(*BLUE)
    c.rect(0, H - 38*mm, W, 38*mm, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont('Helvetica-Bold', 22)
    type_label = {'word': 'Word Assessment', 'rule': 'Rule Reassessment',
                  'homophone': 'Homophone Assessment'}.get(assessment_type, 'Assessment')
    c.drawCentredString(W/2, H - 20*mm, f'Digital Session — {type_label}')
    c.setFont('Helvetica', 13)
    c.drawCentredString(W/2, H - 30*mm, f'{week_ref}  ·  {n_pupils} pupils  ·  {n_words} words')

    # QR code — large, centred
    qr = qrcode.QRCode(box_size=10, border=3)
    qr.add_data(url)
    qr.make(fit=True)
    img    = qr.make_image(fill_color='#1a3c6e', back_color='white')
    qr_io  = io.BytesIO()
    img.save(qr_io, format='PNG')
    qr_io.seek(0)
    qr_size = 90*mm
    qr_x    = (W - qr_size) / 2
    qr_y    = H - 38*mm - 16*mm - qr_size
    c.drawImage(ImageReader(qr_io), qr_x, qr_y, qr_size, qr_size)

    # Session ID below QR
    c.setFont('Helvetica-Bold', 18)
    c.setFillColorRGB(*NAVY)
    c.drawCentredString(W/2, qr_y - 14*mm, f'Session: {session_id}')

    # URL — large enough to read from the back of the room
    c.setFont('Helvetica', 13)
    c.setFillColorRGB(0.25, 0.25, 0.25)
    c.drawCentredString(W/2, qr_y - 23*mm, url)

    # Instructions
    instructions = [
        '1.  Open the URL above on a shared iPad (or scan the QR code).',
        '2.  Each pupil picks their name from the list.',
        '3.  Listen — your teacher reads each word aloud.',
        '4.  Type the word, then tap Submit.',
        '5.  When finished, pass the iPad to the next pupil.',
    ]
    c.setFont('Helvetica', 11)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    y = qr_y - 38*mm
    for line in instructions:
        c.drawCentredString(W/2, y, line)
        y -= 8*mm

    c.save()
    buf.seek(0)
    return buf.read()


# ── Teacher: Create assess session ───────────────────────────────────────────

@live_bp.route('/api/live/assess/create', methods=['POST'])
def api_assess_create():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body         = request.get_json(force=True)
        session_type = body.get('type', 'word')   # word | rule | homophone
        cls          = body.get('cls', 'all')
        week_ref     = body.get('week_ref', '')
        # Selectors vary by type
        sections     = body.get('sections', [])    # word assessment
        rule_ids     = body.get('rules', [])       # rule reassessment
        stages       = body.get('stages', [])      # homophone

        # ── Build items list ────────────────────────────────────────────────
        items = []

        if session_type == 'word':
            cloze = _load_cloze_bank()
            from assessment_builder import _all_sections
            all_sec = _all_sections()
            for key in sections:
                if key not in all_sec:
                    continue
                for word in all_sec[key][1]:
                    sentence = cloze.get(word.lower(), '')
                    items.append({'word': word, 'sentence': sentence,
                                  'key': 'word', 'section': key})

        elif session_type == 'rule':
            cloze = _load_rule_cloze()
            for rid in rule_ids:
                entry = cloze.get(rid)
                if not entry:
                    continue
                for s in entry.get('sentences', [])[:2]:
                    items.append({'word': s['word'], 'sentence': s['sentence'],
                                  'key': 'rule', 'rule_id': rid,
                                  'rule_title': entry.get('title', '')})

        elif session_type == 'homophone':
            cloze = _load_rule_cloze()
            rules_by_stage = _homophone_rules_by_stage()
            for stage in sorted(int(s) for s in stages):
                for rid, title, words in rules_by_stage.get(stage, []):
                    entry = cloze.get(rid, {})
                    sentences = {s['word'].lower(): s['sentence']
                                 for s in entry.get('sentences', [])}
                    for word in words:
                        sentence = sentences.get(word.lower(), '')
                        items.append({'word': word, 'sentence': sentence,
                                      'key': 'homophone', 'rule_id': rid,
                                      'options': words})

        if not items:
            return jsonify({'ok': False, 'error': 'No items — check your selection'})

        # ── Build pupil list ────────────────────────────────────────────────
        class_ids = _resolve_classes(cls)
        pupils = []
        for cid in class_ids:
            d = load_class(cid)
            if d:
                for p in d.get('pupils', []):
                    pupils.append({'id': p['id'], 'first': p.get('first', ''),
                                   'last': p.get('last', ''), 'cls': cid})
        pupils.sort(key=lambda p: (p['first'], p['last']))

        if not pupils:
            return jsonify({'ok': False, 'error': 'No pupils found'})

        # ── Save session ────────────────────────────────────────────────────
        session_id   = uuid.uuid4().hex[:8].upper()
        session_data = {
            'session_id': session_id,
            'created_at': datetime.now().isoformat(),
            'week_ref':   week_ref,
            'type':       session_type,
            'items':      items,
            'pupils':     pupils,
        }
        ok = _save_session(session_id, session_data)
        if not ok:
            return jsonify({'ok': False, 'error': 'Could not save session to data repo'})

        base_url = request.host_url.rstrip('/')
        assess_url = f'{base_url}/live/assess/{session_id}'

        return jsonify({
            'ok':          True,
            'session_id':  session_id,
            'url':         assess_url,
            'week_ref':    week_ref,
            'type':        session_type,
            'n_pupils':    len(pupils),
            'n_items':     len(items),
        })
    except Exception as e:
        return _err(e)


# ── Teacher: QR card PDF ──────────────────────────────────────────────────────

@live_bp.route('/api/live/assess/qr/<session_id>')
def api_assess_qr(session_id):
    r = _auth()
    if r: return r
    try:
        sess = _load_session(session_id)
        if not sess:
            return 'Session not found', 404
        base_url   = request.host_url.rstrip('/')
        assess_url = f'{base_url}/live/assess/{session_id}'
        pdf_bytes  = _build_assess_qr_pdf(
            session_id, assess_url,
            sess.get('week_ref', ''),
            sess.get('type', 'word'),
            len(sess.get('pupils', [])),
            len(sess.get('items', [])),
        )
        resp = make_response(pdf_bytes)
        resp.headers['Content-Type']        = 'application/pdf'
        resp.headers['Content-Disposition'] = f'attachment; filename=Assess_{session_id}.pdf'
        return resp
    except Exception as e:
        return str(e), 500


# ── Pupil: Shared assess page ─────────────────────────────────────────────────

@live_bp.route('/live/assess/<session_id>')
def assess_pupil(session_id):
    """No auth — shared iPad URL. Pupils pick their name then type answers."""
    sess = _load_session(session_id)
    if not sess:
        return render_template('live_error.html', msg='Session not found. Ask your teacher.')
    return render_template('live_assess.html',
        session_id=session_id,
        session_type=sess.get('type', 'word'),
        items=sess.get('items', []),
        pupils_json=json.dumps(sess.get('pupils', [])),
        week_ref=sess.get('week_ref', ''))


# ── Teacher: Process assess results ──────────────────────────────────────────

@live_bp.route('/api/live/assess/process', methods=['POST'])
def api_assess_process():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body       = request.get_json(force=True)
        session_id = body.get('session_id', '')
        if not session_id:
            return jsonify({'ok': False, 'error': 'No session_id'})

        sess = _load_session(session_id)
        if not sess:
            return jsonify({'ok': False, 'error': 'Session not found'})

        results = _load_results(session_id)
        if not results:
            return jsonify({'ok': False, 'error': 'No results yet for this session'})

        # Filter to assess-type results only (not bee results in same folder)
        sess_type = sess.get('type', 'word')
        results   = [r2 for r2 in results if r2.get('session_type') == sess_type]

        # Build lookup: pupil_id → result
        result_map = {r2['pupil_id']: r2 for r2 in results}
        week_ref   = sess.get('week_ref', '')
        today      = date.today().strftime('%Y-%m-%d')
        saved, skipped = 0, 0

        for cid in ALL_CLASSES:
            r2 = _req.get(
                f'https://api.github.com/repos/{DATA_REPO}/contents/data/classes/{cid}.json',
                headers=_HDR, timeout=10)
            if r2.status_code != 200:
                continue
            file_data = r2.json()
            sha       = file_data['sha']
            class_obj = json.loads(base64.b64decode(file_data['content']).decode())
            changed   = False

            for p in class_obj.get('pupils', []):
                pid = p['id']
                res = result_map.get(pid)
                if not res:
                    skipped += 1
                    continue

                answers  = res.get('answers', [])
                ans_map  = {a['word'].lower(): a.get('correct', False) for a in answers}

                # ── Word assessment ──────────────────────────────────────────
                if sess_type == 'word':
                    all_words = {item['word'].lower(): False
                                 for item in sess.get('items', [])}
                    for word, correct in ans_map.items():
                        if word in all_words:
                            all_words[word] = correct
                    mastered = set(p.get('mastered', []))
                    for word, correct in all_words.items():
                        if correct:
                            mastered.add(word)
                        else:
                            mastered.discard(word)
                    p['mastered'] = sorted(mastered)
                    pos = 0
                    for wi, (w, *_) in enumerate(WORD_BANK):
                        if w not in mastered:
                            pos = wi
                            break
                    else:
                        pos = len(WORD_BANK)
                    p['word_pos'] = pos

                # ── Rule reassessment ────────────────────────────────────────
                elif sess_type == 'rule':
                    rule_conf = p.setdefault('rule_confidence', {})
                    # Group items by rule_id
                    rule_items = {}
                    for item in sess.get('items', []):
                        rid = item.get('rule_id', '')
                        rule_items.setdefault(rid, []).append(item['word'])

                    for rid, words in rule_items.items():
                        total   = len(words)
                        correct = sum(1 for w in words if ans_map.get(w.lower(), False))
                        score   = round(correct / total * 100) if total else 0
                        if score >= 90:
                            status = 'full'
                        elif score >= 60:
                            status = 'partial'
                        else:
                            status = 'none'
                        entry = {
                            'week':    week_ref,
                            'date':    today,
                            'correct': correct,
                            'total':   total,
                            'score':   score,
                            'status':  status,
                        }
                        rule_conf.setdefault(rid, []).append(entry)
                    p['rule_confidence'] = rule_conf

                # ── Homophone assessment ─────────────────────────────────────
                elif sess_type == 'homophone':
                    mastered_h = set(p.get('homophone_mastered', []))
                    # Initialise all tested words as False
                    all_hp = {item['word'].lower(): False for item in sess.get('items', [])}
                    for word, correct in ans_map.items():
                        if word in all_hp:
                            all_hp[word] = correct
                    for word, correct in all_hp.items():
                        if correct:
                            mastered_h.add(word)
                        else:
                            mastered_h.discard(word)
                    p['homophone_mastered'] = sorted(mastered_h)

                    # History by stage
                    hp_hist = p.setdefault('homophone_history', {})
                    stage_items = {}
                    for item in sess.get('items', []):
                        rid   = item.get('rule_id', '')
                        stage = rid.split('-')[0] if rid else '?'
                        stage_items.setdefault(stage, []).append(item['word'])
                    for stage, words in stage_items.items():
                        total   = len(words)
                        correct = sum(1 for w in words if ans_map.get(w.lower(), False))
                        score   = round(correct / total * 100) if total else 0
                        status  = 'confident' if score >= 90 else ('partial' if score >= 60 else 'developing')
                        hp_hist.setdefault(stage, []).append({
                            'week': week_ref, 'date': today,
                            'correct': correct, 'total': total,
                            'score': score, 'status': status,
                        })
                    p['homophone_history'] = hp_hist

                saved   += 1
                changed  = True

            if changed:
                content = base64.b64encode(
                    json.dumps(class_obj, indent=2, ensure_ascii=False).encode()).decode()
                _req.put(
                    f'https://api.github.com/repos/{DATA_REPO}/contents/data/classes/{cid}.json',
                    headers=_HDR,
                    json={'message': f'Digital assess {session_id} ({sess_type}) import',
                          'content': content, 'sha': sha, 'branch': 'main'},
                    timeout=15)

        return jsonify({'ok': True, 'saved': saved, 'skipped': skipped,
                        'total_results': len(results)})
    except Exception as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION MANAGEMENT  (/sessions)
# ═══════════════════════════════════════════════════════════════════════════════

@live_bp.route('/sessions')
def session_management():
    r = _auth()
    if r: return r
    return render_template('live_sessions.html')


@live_bp.route('/api/sessions/list')
def api_sessions_list():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        # Load all session files
        sess_r = _req.get(
            f'https://api.github.com/repos/{DATA_REPO}/contents/data/sessions',
            headers=_HDR, timeout=10)
        sessions_raw = []
        if sess_r.status_code == 200:
            for f in sess_r.json():
                if not f['name'].endswith('.json'):
                    continue
                r2 = _req.get(f['download_url'], timeout=10)
                if r2.status_code == 200:
                    try:
                        sessions_raw.append(r2.json())
                    except Exception:
                        pass

        # Load results directory — build {session_id: n_results}
        res_r = _req.get(
            f'https://api.github.com/repos/{DATA_REPO}/contents/data/results',
            headers=_HDR, timeout=10)
        result_counts = {}
        if res_r.status_code == 200:
            for f in res_r.json():
                if not f['name'].endswith('.json'):
                    continue
                parts = f['name'].replace('.json', '').rsplit('_', 1)
                if len(parts) == 2:
                    sid = parts[0]
                    result_counts[sid] = result_counts.get(sid, 0) + 1

        # Build response list
        out = []
        for s in sessions_raw:
            sid      = s.get('session_id', '')
            archived = s.get('archived', False)
            n_res    = result_counts.get(sid, 0)
            n_pupils = len(s.get('pupils', []))
            sess_type = s.get('type', 'spelling_bee')
            out.append({
                'session_id':  sid,
                'type':        sess_type,
                'week_ref':    s.get('week_ref', ''),
                'created_at':  s.get('created_at', ''),
                'n_pupils':    n_pupils,
                'n_items':     len(s.get('items', [])),
                'n_results':   n_res,
                'archived':    archived,
                'complete':    n_res >= n_pupils and n_pupils > 0,
            })

        # Sort newest first
        out.sort(key=lambda x: x['created_at'], reverse=True)
        return jsonify({'ok': True, 'sessions': out})
    except Exception as e:
        return _err(e)


@live_bp.route('/api/sessions/archive', methods=['POST'])
def api_sessions_archive():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body       = request.get_json(force=True)
        session_id = body.get('session_id', '')
        archived   = body.get('archived', True)
        if not session_id:
            return jsonify({'ok': False, 'error': 'No session_id'})

        path = f'data/sessions/{session_id}.json'
        r2 = _req.get(
            f'https://api.github.com/repos/{DATA_REPO}/contents/{path}',
            headers=_HDR, timeout=10)
        if r2.status_code != 200:
            return jsonify({'ok': False, 'error': 'Session not found'})

        file_data  = r2.json()
        sha        = file_data['sha']
        sess       = json.loads(base64.b64decode(file_data['content']).decode())
        sess['archived'] = archived
        content    = base64.b64encode(json.dumps(sess, indent=2).encode()).decode()
        verb       = 'Archive' if archived else 'Unarchive'
        _req.put(
            f'https://api.github.com/repos/{DATA_REPO}/contents/{path}',
            headers=_HDR,
            json={'message': f'{verb} session {session_id}',
                  'content': content, 'sha': sha, 'branch': 'main'},
            timeout=15)
        return jsonify({'ok': True, 'archived': archived})
    except Exception as e:
        return _err(e)

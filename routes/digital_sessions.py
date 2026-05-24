import os, json, base64, uuid
from datetime import datetime, date
import requests as _req
from flask import (Blueprint, render_template, request, jsonify,
                   session, redirect, url_for, send_file, make_response)
from data_manager import load_class, load_weekly_config, ALL_CLASSES
from word_bank import WORD_BANK
from spelling_rules import SPELLING_RULES

live_bp = Blueprint('live', __name__)

PAT       = os.environ.get('GITHUB_TOKEN', '')
DATA_REPO = os.environ.get('DATA_REPO', 'wallscourtfarm/spelling-homelearning')
_HDR      = {'Authorization': f'token {PAT}', 'Accept': 'application/vnd.github.v3+json'}

WB = [w[0] for w in WORD_BANK]

CLASS_OPTIONS = [('all', 'Y4 ALL'), ('Y4_IM', 'Y4 IM'), ('Y4_WU', 'Y4 WU')]


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
    cfg  = wc.get('classes', {}).get(cls.replace('all', 'Y4_IM'), {})
    words = []
    for key in ('main_rule_id', 'revision_rule_id'):
        rid = cfg.get(key, '')
        if rid:
            try:
                stage, step = int(rid.split('-')[0]), int(rid.split('-')[1])
                rule = next((r for r in SPELLING_RULES if r[0]==stage and r[1]==step), None)
                if rule: words.extend(rule[3])
            except Exception:
                pass
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
    r = _auth()
    if r: return r
    cls = request.args.get('cls', 'Y4_IM')
    if cls not in [c[0] for c in CLASS_OPTIONS]: cls = 'Y4_IM'
    wc       = load_weekly_config()
    week_ref = wc.get('week_ref', 'TxWy')
    pupils   = _load_pupils(cls if cls != 'all' else 'Y4_IM')
    paired   = [p for p in pupils if p.get('pair_id')]
    rule_wds = _rule_words(wc, cls)
    return render_template('live_bee.html',
        cls=cls, class_options=CLASS_OPTIONS, week_ref=week_ref,
        n_pupils=len(pupils), n_paired=len(paired),
        n_words=5 + len(rule_wds), rule_words=rule_wds)


@live_bp.route('/api/live/bee/create', methods=['POST'])
def api_bee_create():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body     = request.get_json(force=True)
        cls      = body.get('cls', 'Y4_IM')
        wc       = load_weekly_config()
        week_ref = wc.get('week_ref', '')
        rule_wds = _rule_words(wc, cls)

        class_ids = ALL_CLASSES if cls == 'all' else [cls]
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
        PAD   = 5 * mm
        words = [it['word'] for it in p_rec.get('items', [])]
        n_wds = len(words)

        # Colour bar at top
        colour_rgb = hex_to_rgb(p_rec.get('pair_colour') or '#1798d3')
        c.setFillColorRGB(*colour_rgb)
        c.rect(cx, cy - 10 * mm, col_w, 10 * mm, fill=1, stroke=0)

        # Name
        c.setFillColorRGB(1, 1, 1)
        c.setFont('Helvetica-Bold', 13)
        name = f"{p_rec['first']} {p_rec.get('last', '')}".strip()
        c.drawCentredString(cx + col_w / 2, cy - 7.5 * mm, name)

        # Partner line
        partner = p_rec.get('partner_name', '')
        if partner:
            c.setFont('Helvetica', 8)
            c.setFillColorRGB(0.9, 0.9, 0.9)
            c.drawCentredString(cx + col_w / 2, cy - 9.5 * mm, f'Partner: {partner}')

        # QR code
        url    = f'{base_url}/live/bee/{session_id}/{p_rec["id"]}'
        qr     = qrcode.QRCode(box_size=5, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img    = qr.make_image(fill_color='#1a3c6e', back_color='white')
        qr_io  = __import__('io').BytesIO()
        img.save(qr_io, format='PNG')
        qr_io.seek(0)
        qr_size = 26 * mm
        qr_x    = cx + PAD
        qr_y    = cy - 10 * mm - qr_size - 2 * mm
        c.drawImage(ImageReader(qr_io), qr_x, qr_y, qr_size, qr_size)

        # Week ref + session ID beside QR
        c.setFont('Helvetica', 6.5)
        c.setFillColorRGB(*NAVY)
        info_x = qr_x + qr_size + 3 * mm
        c.drawString(info_x, qr_y + qr_size - 8, f'Session: {session_id}')
        if week_ref:
            c.drawString(info_x, qr_y + qr_size - 15, week_ref)
        c.setFont('Helvetica', 6)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawString(info_x, qr_y + 2, 'Scan to start →')

        # Word list
        word_top = qr_y - 2 * mm
        word_h   = min(4.2 * mm, (word_top - (cy - row_h + PAD)) / max(n_wds, 1))
        for i, word in enumerate(words):
            wy = word_top - i * word_h
            if i == 5:
                # Dashed line between key spellings and rule words
                c.setStrokeColorRGB(0.7, 0.7, 0.7)
                c.setLineWidth(0.3)
                c.setDash([2, 2])
                c.line(cx + PAD, wy + word_h * 0.8, cx + col_w - PAD, wy + word_h * 0.8)
                c.setDash()
            fs = 9 if n_wds <= 8 else 7.5
            c.setFont('Helvetica', fs)
            c.setFillColorRGB(*(NAVY if i < 5 else (0.22, 0.22, 0.52)))
            c.drawString(cx + PAD, wy, f'{i + 1}.  {word}')

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
        items_json=json.dumps(pupil.get('items', [])),
        week_ref=sess.get('week_ref', ''))


# ── Pupil: Submit result ──────────────────────────────────────────────────────

@live_bp.route('/api/live/submit', methods=['POST'])
def api_live_submit():
    """Save pupil assessment result (called by JS on pupil's device)."""
    try:
        body       = request.get_json(force=True)
        session_id = body.get('session_id', '')
        pupil_id   = body.get('pupil_id', '')
        answers    = body.get('answers', [])  # [{word, typed, correct}]
        sess_type  = body.get('session_type', 'spelling_bee')

        if not session_id or not pupil_id:
            return jsonify({'ok': False, 'error': 'Missing session_id or pupil_id'})

        correct = sum(1 for a in answers if a.get('correct'))
        total   = len(answers)

        result = {
            'session_id':   session_id,
            'pupil_id':     pupil_id,
            'name':         body.get('name', ''),
            'week_ref':     body.get('week_ref', ''),
            'session_type': sess_type,
            'submitted':    datetime.now().isoformat(),
            'correct':      correct,
            'total':        total,
            'score_pct':    round(correct / total * 100) if total else 0,
            'answers':      answers,
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

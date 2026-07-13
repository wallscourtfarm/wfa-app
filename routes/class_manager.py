"""
routes/class_manager.py
Pupil and class management: add, edit, remove, move, pair.
"""
import os, json, base64, traceback
import requests as _req
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import (ALL_CLASSES, YEAR_GROUP_CLASSES, load_class,
                          get_class_options, get_class_options_for_year, get_year_group,
                          YEAR_WORD_ZONE, update_teacher_label, bulk_import_pupils, year_end_rollover)

cm_bp = Blueprint('class_manager', __name__)

PAT       = os.environ.get('GITHUB_TOKEN', '')
DATA_REPO = os.environ.get('DATA_REPO', 'wallscourtfarm/spelling-homelearning')
_HDR      = {'Authorization': f'token {PAT}', 'Accept': 'application/vnd.github.v3+json'}

CLASS_OPTIONS  = get_class_options(include_all_per_year=False)
TT_SETS        = ['2', '5', '4', '8', '3', '6', '9', '7', '11', '12', 'All']
PAIR_COLOURS = [
    # Palette designed for maximum print distinctiveness.
    # Only one colour per hue family; within-family members differ by lightness > 30%.
    {'hex': '#C62828', 'name': 'Red'},         # vivid mid-red
    {'hex': '#E65100', 'name': 'Orange'},       # deep orange
    {'hex': '#F9A825', 'name': 'Gold'},         # warm golden yellow
    {'hex': '#827717', 'name': 'Olive'},        # dark yellow-olive (clearly muted vs Gold)
    {'hex': '#2E7D32', 'name': 'Green'},        # pure mid-green
    {'hex': '#558B2F', 'name': 'Lime'},         # bright yellow-green (lighter/warmer than Green)
    {'hex': '#00695C', 'name': 'Teal'},         # blue-green (distinct hue from Green)
    {'hex': '#0277BD', 'name': 'Blue'},         # medium cobalt blue
    {'hex': '#1A237E', 'name': 'Navy'},         # very dark blue (clearly darker than Blue)
    {'hex': '#6A1B9A', 'name': 'Purple'},       # vivid purple (clearly different hue from Blue)
    {'hex': '#AD1457', 'name': 'Pink'},         # deep cerise-pink
    {'hex': '#B71C1C', 'name': 'Crimson'},      # dark wine-red (clearly darker than Red)
    {'hex': '#5D4037', 'name': 'Brown'},        # warm mid-brown
    {'hex': '#37474F', 'name': 'Slate'},        # dark blue-grey (neutral vs Blue)
    {'hex': '#BF360C', 'name': 'Rust'},         # red-brown-orange (between Red and Orange)
    {'hex': '#4A148C', 'name': 'Indigo'},       # deep violet (between Navy and Purple)
    {'hex': '#004D40', 'name': 'Forest'},       # very dark teal-green (clearly darker than Teal)
    {'hex': '#E91E63', 'name': 'Cerise'},       # bright hot-pink (clearly brighter than Pink)
    {'hex': '#EF6C00', 'name': 'Amber'},        # bright amber (lighter/cleaner than Orange)
    {'hex': '#795548', 'name': 'Mocha'},        # light warm tan-brown (lighter than Brown)
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _auth():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))

def _err(e):
    return jsonify({'ok': False, 'error': str(e), 'detail': traceback.format_exc()})

def _load_class_file(cls_id):
    """Returns (class_obj, sha) direct from GitHub."""
    r = _req.get(
        f'https://api.github.com/repos/{DATA_REPO}/contents/data/classes/{cls_id}.json',
        headers=_HDR, timeout=10)
    if r.status_code == 200:
        fd  = r.json()
        obj = json.loads(base64.b64decode(fd['content']).decode())
        return obj, fd['sha']
    return None, None

def _save_class_file(cls_id, class_obj, sha, message):
    content = base64.b64encode(
        json.dumps(class_obj, indent=2, ensure_ascii=False).encode()).decode()
    r = _req.put(
        f'https://api.github.com/repos/{DATA_REPO}/contents/data/classes/{cls_id}.json',
        headers=_HDR,
        json={'message': message, 'content': content, 'sha': sha, 'branch': 'main'},
        timeout=15)
    return r.status_code in (200, 201)

def _all_pupils_map():
    """Returns {pupil_id: {first, last, cls_id}} across all classes."""
    result = {}
    for cid in ALL_CLASSES:
        obj, _ = _load_class_file(cid)
        if obj:
            for p in obj.get('pupils', []):
                result[p['id']] = {
                    'first': p.get('first', ''),
                    'last':  p.get('last', ''),
                    'cls_id': cid,
                }
    return result

def _next_pupil_id():
    """Find the highest p-number across all classes and return the next one."""
    max_n = 0
    for cid in ALL_CLASSES:
        obj, _ = _load_class_file(cid)
        if obj:
            for p in obj.get('pupils', []):
                pid = p.get('id', '')
                if pid.startswith('p') and pid[1:].isdigit():
                    max_n = max(max_n, int(pid[1:]))
    return f'p{max_n + 1:02d}'

def _cls_short(cls_id):
    """4CK -> CK, 5IM -> IM (strips leading year digit)"""
    return cls_id.lstrip('0123456789') if cls_id else cls_id


# ── Page ──────────────────────────────────────────────────────────────────────

@cm_bp.route('/class-manager')
def class_manager():
    r = _auth()
    if r: return r
    yr    = session.get('year_group', '4')
    opts  = get_class_options_for_year(yr, include_all=False)
    valid = [c[0] for c in opts]
    cls   = request.args.get('cls', YEAR_GROUP_CLASSES.get(yr, ['4CK'])[0])
    if cls not in valid:
        cls = YEAR_GROUP_CLASSES.get(yr, ['4CK'])[0]
    return render_template('class_manager.html',
        cls=cls, class_options=opts,
        tt_sets=TT_SETS, pair_colours=PAIR_COLOURS)


# ── API: List pupils ──────────────────────────────────────────────────────────

@cm_bp.route('/api/class/list')
def api_class_list():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    yr  = session.get('year_group', '4')
    cls = request.args.get('cls', YEAR_GROUP_CLASSES.get(yr, ['4CK'])[0])
    try:
        id_map = _all_pupils_map()   # for partner name lookup

        obj, _ = _load_class_file(cls)
        if not obj:
            return jsonify({'ok': False, 'error': f'Could not load {cls}'}), 404

        pupils = []
        for p in obj.get('pupils', []):
            pid     = p.get('pair_id', '')
            partner = id_map.get(pid, {})
            pupils.append({
                'id':           p['id'],
                'first':        p.get('first', ''),
                'last':         p.get('last', ''),
                'group':        p.get('group', 'main'),
                'tt_set':       str(p.get('tt_set', '2')),
                'tt_mode':      p.get('tt_mode', 'x'),
                'pair_id':           pid,
                'pair_colour':       p.get('pair_colour', ''),
                'pair_colour_name':  p.get('pair_colour_name', ''),
                'partner_name': f"{partner.get('first','')} {partner.get('last','')}".strip() if partner else '',
                'partner_cls':  partner.get('cls_id', '') if partner else '',
                'table':        str(p.get('table', '')),
                'adapted_hl':    bool(p.get('adapted_hl', False)),
                'home_language': p.get('home_language', ''),
                'cls':          p.get('cls', _cls_short(cls)),
                'word_pos':     p.get('word_pos', 0),
            })

        pupils.sort(key=lambda p: (p['first'].lower(), p['last'].lower()))

        # Cross-class pupils for pairing selector
        all_for_pairing = [
            {'id': pid, 'first': v['first'], 'last': v['last'], 'cls_id': v['cls_id']}
            for pid, v in id_map.items()
        ]
        all_for_pairing.sort(key=lambda p: (p['first'].lower(), p['last'].lower()))

        return jsonify({'ok': True, 'pupils': pupils,
                        'all_pupils': all_for_pairing, 'cls': cls})
    except Exception as e:
        return _err(e)


# ── API: Update pupil ─────────────────────────────────────────────────────────

@cm_bp.route('/api/class/pupil/update', methods=['POST'])
def api_pupil_update():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body      = request.get_json(force=True)
        cls       = body.get('cls', '4CK')
        pupil_id  = body.get('pupil_id', '')
        changes   = body.get('changes', {})

        ALLOWED = {'first', 'last', 'group', 'tt_set', 'tt_mode',
                   'table', 'adapted_hl', 'ss_user', 'ss_pass', 'language', 'home_language'}
        changes = {k: v for k, v in changes.items() if k in ALLOWED}

        obj, sha = _load_class_file(cls)
        if not obj:
            return jsonify({'ok': False, 'error': f'Could not load {cls}'})

        found = False
        for p in obj.get('pupils', []):
            if p['id'] == pupil_id:
                p.update(changes)
                if 'adapted_hl' in changes:
                    p['adapted_hl'] = bool(changes['adapted_hl'])
                found = True
                break

        if not found:
            return jsonify({'ok': False, 'error': f'Pupil {pupil_id} not found in {cls}'})

        name = next((f"{p.get('first','')} {p.get('last','')}".strip()
                     for p in obj['pupils'] if p['id'] == pupil_id), pupil_id)
        ok = _save_class_file(cls, obj, sha, f'Edit pupil {name} ({pupil_id})')
        return jsonify({'ok': ok})
    except Exception as e:
        return _err(e)


# ── API: Add pupil ────────────────────────────────────────────────────────────

@cm_bp.route('/api/class/pupil/add', methods=['POST'])
def api_pupil_add():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body  = request.get_json(force=True)
        cls   = body.get('cls', '4CK')
        first = body.get('first', '').strip()
        last  = body.get('last', '').strip()

        if not first:
            return jsonify({'ok': False, 'error': 'First name is required'})

        obj, sha = _load_class_file(cls)
        if not obj:
            return jsonify({'ok': False, 'error': f'Could not load {cls}'})

        yr        = get_year_group(cls) or '4'
        start_pos = YEAR_WORD_ZONE.get(yr, 185)
        new_id    = _next_pupil_id()
        new_pupil = {
            'id':              new_id,
            'first':           first,
            'last':            last,
            'cls':             _cls_short(cls),
            'group':           body.get('group', 'main'),
            'tt_set':          body.get('tt_set', '2'),
            'tt_mode':         'x',
            'table':           body.get('table', ''),
            'adapted_hl':      bool(body.get('adapted_hl', False)),
            'language':        body.get('language', ''),
            'pair_id':         '',
            'pair_colour':     '',
            'word_pos':        start_pos,
            'mastered':        [],
            'rule_confidence': {},
            'ss_user':           '',
            'ss_pass':           '',
            'homophone_mastered': [],
            'homophone_history':  {},
        }
        obj.setdefault('pupils', []).append(new_pupil)
        ok = _save_class_file(cls, obj, sha, f'Add pupil {first} {last} ({new_id})')
        return jsonify({'ok': ok, 'pupil_id': new_id})
    except Exception as e:
        return _err(e)


# ── API: Remove pupil ─────────────────────────────────────────────────────────

@cm_bp.route('/api/class/pupil/remove', methods=['POST'])
def api_pupil_remove():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body     = request.get_json(force=True)
        cls      = body.get('cls', '4CK')
        pupil_id = body.get('pupil_id', '')

        obj, sha = _load_class_file(cls)
        if not obj:
            return jsonify({'ok': False, 'error': f'Could not load {cls}'})

        target = next((p for p in obj.get('pupils', []) if p['id'] == pupil_id), None)
        if not target:
            return jsonify({'ok': False, 'error': f'Pupil {pupil_id} not found'})

        name = f"{target.get('first','')} {target.get('last','')}".strip()

        # If they have a pair, clear the partner's pair_id too (may be in other class)
        partner_id = target.get('pair_id', '')
        if partner_id:
            _clear_pair_field(partner_id, pupil_id)

        obj['pupils'] = [p for p in obj['pupils'] if p['id'] != pupil_id]
        ok = _save_class_file(cls, obj, sha, f'Remove pupil {name} ({pupil_id})')
        return jsonify({'ok': ok, 'name': name})
    except Exception as e:
        return _err(e)


# ── API: Move pupil ───────────────────────────────────────────────────────────

@cm_bp.route('/api/class/pupil/move', methods=['POST'])
def api_pupil_move():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body     = request.get_json(force=True)
        from_cls = body.get('from_cls', '')
        to_cls   = body.get('to_cls', '')
        pupil_id = body.get('pupil_id', '')

        if from_cls == to_cls:
            return jsonify({'ok': False, 'error': 'Source and destination are the same'})

        src, src_sha = _load_class_file(from_cls)
        dst, dst_sha = _load_class_file(to_cls)
        if not src or not dst:
            return jsonify({'ok': False, 'error': 'Could not load class files'})

        target = next((p for p in src.get('pupils', []) if p['id'] == pupil_id), None)
        if not target:
            return jsonify({'ok': False, 'error': f'Pupil {pupil_id} not found in {from_cls}'})

        name = f"{target.get('first','')} {target.get('last','')}".strip()

        # Update cls field and move
        target['cls'] = _cls_short(to_cls)
        src['pupils'] = [p for p in src['pupils'] if p['id'] != pupil_id]
        dst.setdefault('pupils', []).append(target)

        ok1 = _save_class_file(from_cls, src, src_sha, f'Move {name} out to {to_cls}')
        dst2, dst_sha2 = _load_class_file(to_cls)   # re-fetch sha after first write
        ok2 = _save_class_file(to_cls, dst, dst_sha, f'Move {name} in from {from_cls}')

        return jsonify({'ok': ok1 and ok2, 'name': name})
    except Exception as e:
        return _err(e)


# ── API: Set pair ─────────────────────────────────────────────────────────────

@cm_bp.route('/api/class/pair', methods=['POST'])
def api_pair():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body         = request.get_json(force=True)
        pupil_a_id   = body.get('pupil_a', '')
        pupil_b_id   = body.get('pupil_b', '')
        colour       = body.get('colour', '#0070C0')
        colour_name  = next((pc['name'] for pc in PAIR_COLOURS
                             if pc['hex'].upper() == colour.upper()), '')

        if not pupil_a_id or not pupil_b_id or pupil_a_id == pupil_b_id:
            return jsonify({'ok': False, 'error': 'Invalid pair selection'})

        # Locate both pupils (may be in different classes)
        id_map = _all_pupils_map()
        cls_a  = id_map.get(pupil_a_id, {}).get('cls_id')
        cls_b  = id_map.get(pupil_b_id, {}).get('cls_id')

        if not cls_a or not cls_b:
            return jsonify({'ok': False, 'error': 'Could not locate one or both pupils'})

        # Load relevant class files (may be the same)
        classes_to_update = list(dict.fromkeys([cls_a, cls_b]))   # dedupe, preserve order
        files = {}
        for cid in classes_to_update:
            obj, sha = _load_class_file(cid)
            files[cid] = (obj, sha)

        for cid, (obj, sha) in files.items():
            for p in obj.get('pupils', []):
                if p['id'] == pupil_a_id:
                    p['pair_id'] = pupil_b_id
                    p['pair_colour'] = colour
                    p['pair_colour_name'] = colour_name
                elif p['id'] == pupil_b_id:
                    p['pair_id'] = pupil_a_id
                    p['pair_colour'] = colour
                    p['pair_colour_name'] = colour_name
            name_a = id_map[pupil_a_id]['first']
            name_b = id_map[pupil_b_id]['first']
            _save_class_file(cid, obj, sha, f'Pair {name_a} ↔ {name_b}')

        return jsonify({'ok': True})
    except Exception as e:
        return _err(e)


# ── API: Remove pair ──────────────────────────────────────────────────────────

@cm_bp.route('/api/class/unpair', methods=['POST'])
def api_unpair():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body     = request.get_json(force=True)
        pupil_id = body.get('pupil_id', '')

        id_map   = _all_pupils_map()
        cls_a    = id_map.get(pupil_id, {}).get('cls_id')
        if not cls_a:
            return jsonify({'ok': False, 'error': 'Pupil not found'})

        obj_a, sha_a = _load_class_file(cls_a)
        partner_id   = next((p.get('pair_id','') for p in obj_a.get('pupils',[])
                             if p['id'] == pupil_id), '')

        # Clear pair on pupil A
        for p in obj_a.get('pupils', []):
            if p['id'] == pupil_id:
                p['pair_id']    = ''
                p['pair_colour'] = ''
        name = id_map[pupil_id]['first']
        _save_class_file(cls_a, obj_a, sha_a, f'Unpair {name}')

        # Clear pair on partner (may be different class)
        if partner_id:
            _clear_pair_field(partner_id, pupil_id)

        return jsonify({'ok': True})
    except Exception as e:
        return _err(e)


# ── Internal: clear one side of a broken pair ─────────────────────────────────

def _clear_pair_field(pupil_id, former_pair_id):
    """Remove pair_id/pair_colour from a pupil who was paired with former_pair_id."""
    id_map = _all_pupils_map()
    cid    = id_map.get(pupil_id, {}).get('cls_id')
    if not cid:
        return
    obj, sha = _load_class_file(cid)
    if not obj:
        return
    for p in obj.get('pupils', []):
        if p['id'] == pupil_id and p.get('pair_id') == former_pair_id:
            p['pair_id']    = ''
            p['pair_colour'] = ''
    _save_class_file(cid, obj, sha, f'Clear stale pair ref on {pupil_id}')


# ── API: Update teacher label ─────────────────────────────────────────────────

@cm_bp.route('/api/class/teacher/update', methods=['POST'])
def api_teacher_update():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body         = request.get_json(force=True)
        class_id     = body.get('class_id', '')
        teacher_code = body.get('teacher_code', '').strip().upper()
        teacher_name = body.get('teacher_name', '').strip()
        if not class_id or not teacher_code:
            return jsonify({'ok': False, 'error': 'class_id and teacher_code are required'})
        result = update_teacher_label(class_id, teacher_code, teacher_name)
        return jsonify(result)
    except Exception as e:
        return _err(e)


# ── API: CSV bulk import ──────────────────────────────────────────────────────

@cm_bp.route('/api/class/import', methods=['POST'])
def api_bulk_import():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body     = request.get_json(force=True)
        class_id = body.get('class_id', '')
        csv_text = body.get('csv', '')
        if not class_id or not csv_text.strip():
            return jsonify({'ok': False, 'error': 'class_id and csv are required'})
        result = bulk_import_pupils(class_id, csv_text)
        return jsonify(result)
    except Exception as e:
        return _err(e)


# ── API: Year-end rollover ────────────────────────────────────────────────────

@cm_bp.route('/api/rollover', methods=['POST'])
def api_rollover():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body       = request.get_json(force=True)
        year_group = body.get('year_group', '')
        if not year_group:
            return jsonify({'ok': False, 'error': 'year_group is required'})
        result = year_end_rollover(str(year_group))
        return jsonify(result)
    except Exception as e:
        return _err(e)


# ── API: Mastery import ───────────────────────────────────────────────────────

@cm_bp.route('/api/class/import-mastery', methods=['POST'])
def api_import_mastery():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        from data_manager import import_pupils_with_mastery
        body        = request.get_json(force=True)
        year_group  = body.get('year_group', session.get('year_group', '4'))
        csv_text    = body.get('csv', '')
        on_conflict = body.get('on_conflict', 'merge')
        if not csv_text.strip():
            return jsonify({'ok': False, 'error': 'No CSV data provided'})
        result = import_pupils_with_mastery(year_group, csv_text, on_conflict)
        return jsonify(result)
    except Exception as e:
        return _err(e)


@cm_bp.route('/api/class/mastery-template')
def api_mastery_template():
    """Download a CSV template for the mastery import."""
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    from flask import Response
    yr      = session.get('year_group', '4')
    classes = YEAR_GROUP_CLASSES.get(yr, [])
    example_cls = classes[0].lstrip('0123456789') if classes else 'IM'
    lines = [
        'First,Last,Class,Mastered',
        f'Example,Pupil,{example_cls},"about accident address after again"',
        f'Another,Learner,{example_cls},"I Mr Mrs about after"',
    ]
    csv_content = '\n'.join(lines)
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=mastery_import_Y{yr}_template.csv'}
    )


@cm_bp.route('/api/class/import-ss-csv', methods=['POST'])
def api_import_ss_csv():
    """
    Parse a Spelling Shed export CSV and match pupils to the app by full name + year group.
    CSV columns: name(0), school_username(4), group(6), password(7).
    Returns a list of matched/unmatched results for review, then applies on confirm.
    """
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        import csv, io, unicodedata

        def normalise(s):
            s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
            return s.lower().strip()

        mode = request.form.get('mode', 'preview')   # 'preview' or 'apply'
        f    = request.files.get('csv_file')
        if not f:
            return jsonify({'ok': False, 'error': 'No file uploaded'})

        text   = f.read().decode('utf-8-sig')
        reader = csv.reader(io.StringIO(text))
        rows   = list(reader)
        if not rows:
            return jsonify({'ok': False, 'error': 'Empty CSV'})

        # Skip header row if present
        data_rows = rows[1:] if rows[0][0].lower() in ('name', 'full name') else rows

        # Parse CSV entries
        ss_entries = []
        for row in data_rows:
            if len(row) < 8:
                continue
            full_name = row[0].strip()
            ss_user   = row[4].strip()
            yr_label  = row[6].strip()          # e.g. "Year 4"
            ss_pass   = row[7].strip()
            if not full_name or not ss_user:
                continue
            # Parse year group number from "Year 4" → "4"
            yr = yr_label.replace('Year ', '').replace('year ', '').strip()
            parts = full_name.split(' ', 1)
            first = parts[0]
            last  = parts[1] if len(parts) > 1 else ''
            ss_entries.append({
                'full_name': full_name,
                'first': first, 'last': last,
                'yr': yr,
                'ss_user': ss_user, 'ss_pass': ss_pass
            })

        # Load all pupils from the data store grouped by class
        from data_manager import YEAR_GROUP_CLASSES, _resolve_classes
        all_class_data = {}
        for yr, classes in YEAR_GROUP_CLASSES.items():
            for cid in classes:
                d = load_class(cid)
                if d:
                    all_class_data[cid] = d

        # Build a flat lookup: (normalised_full_name, yr) → (cid, pupil)
        lookup = {}
        for cid, d in all_class_data.items():
            for p in d.get('pupils', []):
                key = (normalise(f"{p.get('first','')} {p.get('last','')}"),
                       str(p.get('yr') or ''))
                lookup[key] = (cid, p)
                # Also index by year from the class ID (e.g. 4CK → yr='4')
                yr_from_cls = cid[1] if len(cid) > 1 else ''
                lookup[(normalise(f"{p.get('first','')} {p.get('last','')}"), yr_from_cls)] = (cid, p)

        matched   = []
        unmatched = []

        for entry in ss_entries:
            key = (normalise(f"{entry['first']} {entry['last']}"), entry['yr'])
            result = lookup.get(key)

            if not result:
                # Try without year group (looser match)
                for (name_key, _), val in lookup.items():
                    if name_key == normalise(f"{entry['first']} {entry['last']}"):
                        result = val
                        break

            if result:
                cid, pupil = result
                matched.append({
                    'pupil_id': pupil['id'],
                    'cls':      cid,
                    'name':     f"{pupil.get('first','')} {pupil.get('last','')}".strip(),
                    'ss_user':  entry['ss_user'],
                    'ss_pass':  entry['ss_pass'],
                })
            else:
                unmatched.append({
                    'name': entry['full_name'],
                    'yr':   entry['yr'],
                    'ss_user': entry['ss_user'],
                    'ss_pass': entry['ss_pass'],
                })

        if mode == 'preview':
            return jsonify({
                'ok': True,
                'matched':   len(matched),
                'unmatched': len(unmatched),
                'unmatched_names': [u['name'] for u in unmatched],
                'preview':   matched[:5],
            })

        # Apply mode — write credentials back to class files
        updates_by_cls = {}
        for m in matched:
            updates_by_cls.setdefault(m['cls'], []).append(m)

        applied = 0
        for cid, updates in updates_by_cls.items():
            d, sha_c = _load_class_file(cid)
            if not d:
                continue
            id_map = {u['pupil_id']: u for u in updates}
            for p in d.get('pupils', []):
                if p['id'] in id_map:
                    u = id_map[p['id']]
                    p['ss_user'] = u['ss_user']
                    p['ss_pass'] = u['ss_pass']
                    applied += 1
            _save_class_file(cid, d, sha_c, f'Import Spelling Shed credentials ({len(updates)} pupils)')

        return jsonify({'ok': True, 'applied': applied, 'unmatched': len(unmatched),
                        'unmatched_names': [u['name'] for u in unmatched]})

    except Exception as e:
        return _err(e)


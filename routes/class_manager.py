"""
routes/class_manager.py
Pupil and class management: add, edit, remove, move, pair.
"""
import os, json, base64, traceback, random
import requests as _req
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import (ALL_CLASSES, YEAR_GROUP_CLASSES, load_class,
                          get_class_options, get_class_options_for_year,
                          update_teacher_label)
from word_bank import next_active_index
from phonics_bank import PHONICS_SETS

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
    cls   = request.args.get('cls', YEAR_GROUP_CLASSES.get(yr, ['4CC'])[0])
    if cls not in valid:
        cls = YEAR_GROUP_CLASSES.get(yr, ['4CC'])[0]
    return render_template('class_manager.html',
        cls=cls, class_options=opts,
        tt_sets=TT_SETS, pair_colours=PAIR_COLOURS,
        phonics_sets_json=json.dumps(PHONICS_SETS))


# ── API: List pupils ──────────────────────────────────────────────────────────

@cm_bp.route('/api/class/list')
def api_class_list():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    yr  = session.get('year_group', '4')
    cls = request.args.get('cls', YEAR_GROUP_CLASSES.get(yr, ['4CC'])[0])
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
                'us_code':      p.get('us_code', ''),
                'us_pin':       p.get('us_pin', ''),
                'cls':          p.get('cls', _cls_short(cls)),
                'word_pos':     next_active_index(p.get('word_pos', 0), set(p.get('mastered', []))),
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
        cls       = body.get('cls', '4CC')
        pupil_id  = body.get('pupil_id', '')
        changes   = body.get('changes', {})

        # first/last/cls are Bromcom-owned identity fields — set only via
        # Roster Import, never editable per-pupil here.
        ALLOWED = {'group', 'phonics_gpcs', 'tt_set', 'tt_mode',
                   'table', 'adapted_hl', 'us_code', 'us_pin', 'language', 'home_language'}
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


# ── API: Reset all pairings in a class ──────────────────────────────────────────

@cm_bp.route('/api/class/unpair_all', methods=['POST'])
def api_unpair_all():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body   = request.get_json(force=True)
        cls_id = body.get('cls_id', '')
        if not cls_id:
            return jsonify({'ok': False, 'error': 'Missing cls_id'})

        obj, sha = _load_class_file(cls_id)
        if not obj:
            return jsonify({'ok': False, 'error': 'Class not found'})

        pairs = [(p['id'], p['pair_id']) for p in obj.get('pupils', []) if p.get('pair_id')]
        if not pairs:
            return jsonify({'ok': True, 'count': 0})

        own_ids = {p['id'] for p in obj.get('pupils', [])}
        for p in obj.get('pupils', []):
            if p.get('pair_id'):
                p['pair_id']    = ''
                p['pair_colour'] = ''
        _save_class_file(cls_id, obj, sha, f'Reset all pairings for {cls_id}')

        # Clear the other side for any partners who live in a different class
        for own_id, partner_id in pairs:
            if partner_id not in own_ids:
                _clear_pair_field(partner_id, own_id)

        return jsonify({'ok': True, 'count': len(pairs)})
    except Exception as e:
        return _err(e)


# ── Internal: pick colours for a batch of new pairs, avoiding ones in use ──────

def _colour_cycle(existing_pupils):
    used = {p.get('pair_colour') for p in existing_pupils if p.get('pair_colour')}
    available = [c for c in PAIR_COLOURS if c['hex'] not in used] or list(PAIR_COLOURS)
    random.shuffle(available)
    return available + PAIR_COLOURS   # fall back to repeats once we run out of fresh colours


# ── API: Bulk pair from numbered assignments ────────────────────────────────────

@cm_bp.route('/api/class/pair_bulk', methods=['POST'])
def api_pair_bulk():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body        = request.get_json(force=True)
        cls_id      = body.get('cls_id', '')
        assignments = body.get('assignments', {})   # {pupil_id: group_number|None}
        if not cls_id:
            return jsonify({'ok': False, 'error': 'Missing cls_id'})

        obj, sha = _load_class_file(cls_id)
        if not obj:
            return jsonify({'ok': False, 'error': 'Class not found'})
        pupils = obj.get('pupils', [])
        by_id  = {p['id']: p for p in pupils}

        # Only pupils the caller explicitly included (i.e. rendered as a bulk
        # input in this class's table) are eligible to be reconciled — anyone
        # absent from `assignments` (e.g. a cross-class partner not shown on
        # this page) is left completely untouched.
        touched_ids = {pid for pid in assignments if pid in by_id}

        groups = {}
        for pid, num in assignments.items():
            if num in (None, '') or pid not in by_id:
                continue
            groups.setdefault(str(num), []).append(pid)

        bad = {num: ids for num, ids in groups.items() if len(ids) != 2}
        if bad:
            def name(pid):
                p = by_id[pid]
                return f"{p.get('first','')} {p.get('last','')}".strip() or pid
            detail = '; '.join(
                f"#{num} has {len(ids)} pupil(s) ({', '.join(name(i) for i in ids)})"
                for num, ids in bad.items())
            return jsonify({'ok': False, 'error': f'Fix these pair numbers before saving — {detail}'})

        new_pairs = [tuple(ids) for ids in groups.values()]
        desired_partner = {}
        for a, b in new_pairs:
            desired_partner[a] = b
            desired_partner[b] = a

        touched_partner_ids = []   # (partner_id, former_id) for cross-class partners to clear

        # 1. Break any existing pairing that no longer matches the desired state,
        #    but only for pupils this bulk save was actually told about.
        for p in pupils:
            if p['id'] not in touched_ids:
                continue
            cur_partner = p.get('pair_id', '')
            if not cur_partner or desired_partner.get(p['id']) == cur_partner:
                continue
            p['pair_id']          = ''
            p['pair_colour']      = ''
            p['pair_colour_name'] = ''
            if cur_partner not in by_id:
                touched_partner_ids.append((cur_partner, p['id']))

        # 2. Apply the new pairs, auto-assigning colours to any that are genuinely new
        colours   = _colour_cycle(pupils)
        colour_i  = 0
        for a, b in new_pairs:
            pa, pb = by_id[a], by_id[b]
            if pa.get('pair_id') == b and pb.get('pair_id') == a:
                continue   # already correctly paired — leave its colour alone
            colour = colours[colour_i % len(colours)]
            colour_i += 1
            pa['pair_id'], pa['pair_colour'], pa['pair_colour_name'] = b, colour['hex'], colour['name']
            pb['pair_id'], pb['pair_colour'], pb['pair_colour_name'] = a, colour['hex'], colour['name']

        _save_class_file(cls_id, obj, sha, f'Bulk update pairings for {cls_id}')

        # 3. Clear the far side of any cross-class pairing we just broke
        for partner_id, former_id in touched_partner_ids:
            _clear_pair_field(partner_id, former_id)

        return jsonify({'ok': True, 'pairs': len(new_pairs)})
    except Exception as e:
        return _err(e)


# ── API: Randomly pair up everyone currently unpaired in a class ───────────────

@cm_bp.route('/api/class/autopair', methods=['POST'])
def api_autopair():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body   = request.get_json(force=True)
        cls_id = body.get('cls_id', '')
        if not cls_id:
            return jsonify({'ok': False, 'error': 'Missing cls_id'})

        obj, sha = _load_class_file(cls_id)
        if not obj:
            return jsonify({'ok': False, 'error': 'Class not found'})
        pupils = obj.get('pupils', [])

        unpaired = [p for p in pupils if not p.get('pair_id')]
        random.shuffle(unpaired)
        if len(unpaired) < 2:
            return jsonify({'ok': True, 'pairs': 0})

        colours    = _colour_cycle(pupils)
        pairs_made = 0
        for i in range(0, len(unpaired) - 1, 2):
            a, b = unpaired[i], unpaired[i + 1]
            colour = colours[pairs_made % len(colours)]
            a['pair_id'], a['pair_colour'], a['pair_colour_name'] = b['id'], colour['hex'], colour['name']
            b['pair_id'], b['pair_colour'], b['pair_colour_name'] = a['id'], colour['hex'], colour['name']
            pairs_made += 1

        _save_class_file(cls_id, obj, sha, f'Auto-pair {pairs_made} pupil pair(s) in {cls_id}')
        return jsonify({'ok': True, 'pairs': pairs_made})
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


# ── API: Recompute word_pos for existing pupils from their mastered list ───────

@cm_bp.route('/api/admin/word_pos_backfill')
def api_word_pos_backfill():
    """Dry-run by default; pass ?apply=1 to actually save the corrected
    word_pos values. Recomputes every pupil's position from the very start
    of the whole CEW/Key Spelling list, using their real mastered words —
    correcting anyone left at their old year-zone floor by the pre-fix
    add/rollover/import logic (see class_manager.py commit history)."""
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    apply_changes = request.args.get('apply') == '1'
    try:
        changes = []
        for cls_id in ALL_CLASSES:
            obj, sha = _load_class_file(cls_id)
            if not obj:
                continue
            touched = False
            for p in obj.get('pupils', []):
                mastered = set(p.get('mastered', []))
                old_pos  = p.get('word_pos', 0)
                new_pos  = next_active_index(0, mastered)
                if new_pos != old_pos:
                    changes.append({
                        'cls': cls_id, 'id': p['id'],
                        'name': f"{p.get('first','')} {p.get('last','')}".strip(),
                        'group': p.get('group', 'main'),
                        'mastered_count': len(mastered),
                        'old_pos': old_pos, 'new_pos': new_pos,
                    })
                    if apply_changes:
                        p['word_pos'] = new_pos
                        touched = True
            if apply_changes and touched:
                _save_class_file(cls_id, obj, sha, f'Backfill word_pos from mastered list ({cls_id})')
        return jsonify({'ok': True, 'applied': apply_changes, 'count': len(changes), 'changes': changes})
    except Exception as e:
        return _err(e)


# ── API: Roster sync (Bromcom roster via shared-sync bus) ─────────────────────

@cm_bp.route('/api/class/roster-sync', methods=['POST'])
def api_roster_sync():
    """Pull the UPN-keyed roster from the shared-sync bus and merge it into
    every class file: refreshes names/classes, attaches UPNs to any
    not-yet-UPN'd pupils, adds new arrivals and removes (archiving) leavers."""
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        from roster_sync import sync_roster
        result = sync_roster(apply=True)
        return jsonify(result)
    except Exception as e:
        return _err(e)


@cm_bp.route('/api/class/roster-status')
def api_roster_status():
    """Last roster-sync metadata from data/roster_meta.json for the status chip."""
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        r2 = _req.get(f'https://api.github.com/repos/{DATA_REPO}/contents/data/roster_meta.json',
                      headers=_HDR, timeout=10)
        if r2.status_code != 200:
            return jsonify({'ok': True, 'synced': False,
                            'note': 'No roster sync has run yet'})
        obj = json.loads(base64.b64decode(r2.json()['content']).decode())
        return jsonify({'ok': True, 'synced': True, **obj})
    except Exception as e:
        return _err(e)


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


@cm_bp.route('/api/class/import-unlocking-spelling-csv', methods=['POST'])
def api_import_unlocking_spelling_csv():
    """
    Parse a pasted Unlocking Spelling roster (columns: First, Last, Year e.g.
    "Y4", Code, PIN) and match pupils to the app by full name + year group.
    Accepts comma- or tab-separated text (a direct paste from Google Sheets
    is tab-separated) — delimiter is auto-detected.
    Returns a list of matched/unmatched results for review, then applies on confirm.
    """
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        import csv, io, unicodedata

        def normalise(s):
            s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
            return s.lower().strip()

        body = request.get_json(force=True)
        mode = body.get('mode', 'preview')   # 'preview' or 'apply'
        text = body.get('csv', '').lstrip('﻿').strip()
        if not text:
            return jsonify({'ok': False, 'error': 'No data provided'})

        delimiter = '\t' if text.split('\n', 1)[0].count('\t') >= text.split('\n', 1)[0].count(',') else ','
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows   = list(reader)
        if not rows:
            return jsonify({'ok': False, 'error': 'Empty data'})

        # Skip header row if present
        data_rows = rows[1:] if rows[0][0].lower() in ('first name', 'first') else rows

        # Parse CSV entries
        us_entries = []
        for row in data_rows:
            if len(row) < 5:
                continue
            first    = row[0].strip()
            last     = row[1].strip()
            yr_label = row[2].strip()          # e.g. "Y4"
            us_code  = row[3].strip()
            us_pin   = row[4].strip()
            if not first or not us_code:
                continue
            # Parse year group number from "Y4" → "4"
            yr = yr_label.upper().replace('YEAR ', '').replace('Y', '').strip()
            us_entries.append({
                'full_name': f'{first} {last}'.strip(),
                'first': first, 'last': last,
                'yr': yr,
                'us_code': us_code, 'us_pin': us_pin
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
                yr_from_cls = cid[0] if cid else ''
                lookup[(normalise(f"{p.get('first','')} {p.get('last','')}"), yr_from_cls)] = (cid, p)

        matched   = []
        unmatched = []

        for entry in us_entries:
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
                    'us_code':  entry['us_code'],
                    'us_pin':  entry['us_pin'],
                })
            else:
                unmatched.append({
                    'name': entry['full_name'],
                    'yr':   entry['yr'],
                    'us_code': entry['us_code'],
                    'us_pin': entry['us_pin'],
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
                    p['us_code'] = u['us_code']
                    p['us_pin'] = u['us_pin']
                    applied += 1
            _save_class_file(cid, d, sha_c, f'Import Unlocking Spelling credentials ({len(updates)} pupils)')

        return jsonify({'ok': True, 'applied': applied, 'unmatched': len(unmatched),
                        'unmatched_names': [u['name'] for u in unmatched]})

    except Exception as e:
        return _err(e)


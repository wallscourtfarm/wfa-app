"""
data_manager.py
Reads and writes JSON data files stored in wallscourtfarm/spelling-homelearning.
TT data lives inside data/classes/<class_id>.json per pupil.

Environment variables:
    GITHUB_TOKEN  — PAT with repo write access
    DATA_REPO     — e.g. wallscourtfarm/spelling-homelearning
"""

import os
import json
import base64
import requests

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
DATA_REPO    = os.environ.get('DATA_REPO', 'wallscourtfarm/spelling-homelearning')
BRANCH       = 'main'

HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
}
BASE_URL = f'https://api.github.com/repos/{DATA_REPO}/contents'


# ── Two-step TT progression ───────────────────────────────────────────────────
TT_ORDER = ['2', '5', '4', '8', '3', '6', '9', '7', '11', '12', 'All']

def advance_tt(tt_set, tt_mode='x'):
    """
    Two-step progression:
      × only  →  × and ÷ (same table)
      × and ÷ →  × only (next table)
    Caps at All×÷.
    Returns (new_set, new_mode).
    """
    if str(tt_set) == 'All' and tt_mode == 'xd':
        return ('All', 'xd')
    if tt_mode != 'xd':
        return (tt_set, 'xd')
    try:
        i = TT_ORDER.index(str(tt_set))
        new_set = TT_ORDER[i + 1] if i + 1 < len(TT_ORDER) else tt_set
    except ValueError:
        new_set = tt_set
    return (new_set, 'x')


def tt_label(tt_set, tt_mode):
    """Human-readable stage label e.g. '3×' or '3×÷'."""
    symbol = '×÷' if tt_mode == 'xd' else '×'
    return f'{tt_set}{symbol}'


# ── GitHub helpers ────────────────────────────────────────────────────────────

def _get_file(path):
    """Return (parsed_json, sha) or (None, None)."""
    r = requests.get(f'{BASE_URL}/{path}', headers=HEADERS, timeout=10)
    if r.status_code == 200:
        d = r.json()
        content = json.loads(base64.b64decode(d['content']).decode('utf-8'))
        return content, d['sha']
    return None, None


def _put_file(path, data, sha, message):
    """Write JSON back to GitHub. Returns True on success."""
    content = base64.b64encode(
        json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
    ).decode('utf-8')
    payload = {'message': message, 'content': content, 'sha': sha, 'branch': BRANCH}
    r = requests.put(f'{BASE_URL}/{path}', headers=HEADERS,
                     json=payload, timeout=15)
    return r.status_code in (200, 201)


# ── Class helpers ─────────────────────────────────────────────────────────────

CLASS_PATH = 'data/classes/{class_id}.json'

def load_class(class_id):
    data, _ = _get_file(CLASS_PATH.format(class_id=class_id))
    return data


# ── TT Check ─────────────────────────────────────────────────────────────────

def load_tt_pupils(class_id='Y4_IM'):
    """
    Return list of pupil dicts for TT Check display.
    Each dict: {id, name, tt_set, tt_mode, label}
    """
    data = load_class(class_id)
    if not data:
        return []
    pupils = []
    for p in data.get('pupils', []):
        tt_set  = p.get('tt_set',  '2')
        tt_mode = p.get('tt_mode', 'x')
        name = p.get('first', '?')
        last = p.get('last', '')
        if last:
            name = f'{name} {last}'
        pupils.append({
            'id':      p['id'],
            'name':    name,
            'first':   p.get('first', ''),
            'tt_set':  tt_set,
            'tt_mode': tt_mode,
            'label':   tt_label(tt_set, tt_mode),
        })
    # Sort by table order then name
    def sort_key(p):
        try:
            idx = TT_ORDER.index(str(p['tt_set']))
        except ValueError:
            idx = 99
        xd = 1 if p['tt_mode'] == 'xd' else 0
        return (idx, xd, p['name'].lower())
    return sorted(pupils, key=sort_key)


def advance_tt_pupils(class_id, pupil_ids):
    """
    Atomically advance TT for the given pupil id list.
    Returns {'ok': True, 'count': n} or {'ok': False, 'error': str}.
    """
    path = CLASS_PATH.format(class_id=class_id)
    data, sha = _get_file(path)
    if not data:
        return {'ok': False, 'error': f'Could not load {path}'}
    id_set = set(pupil_ids)
    changed = 0
    for i, p in enumerate(data.get('pupils', [])):
        if p['id'] in id_set:
            ns, nm = advance_tt(p.get('tt_set', '2'), p.get('tt_mode', 'x'))
            data['pupils'][i]['tt_set']  = ns
            data['pupils'][i]['tt_mode'] = nm
            changed += 1
    if changed:
        ok = _put_file(path, data, sha, f'TT advance: {class_id} ({changed} pupils)')
        if not ok:
            return {'ok': False, 'error': 'GitHub write failed'}
    return {'ok': True, 'count': changed}

"""
roster_sync.py — single-source-of-truth roster sync for wfa-app.

Pulls the UPN-keyed pupil roster from the WFA API's Postgres roster
(fed by Roster Import's Bromcom upload) and merges it into the
spelling-homelearning class files:

  1. UPN match   — pupil.upn present and on roster → refresh name/cls
  2. Name match  — pupil without a UPN, exact normalised full-name match
                   on the roster (and the UPN not already claimed) →
                   attach the UPN, refresh name/cls
  3. New pupils  — roster UPNs not seen in any class file → appended to
                   the class file matching their Bromcom class, with a
                   fresh globally-unique p## id
  4. Leavers     — UPN'd pupils absent from the roster are removed and
                   archived to data/archived/roster_leavers.json in the
                   (private) data repo. Pupils without a UPN are never
                   auto-removed, only reported.
  5. Meta        — data/roster_meta.json records the last sync for the
                   status indicator on the Class Manager page.

Safety valve: if the roster has dropped below 80% of the current pupil
count the sync aborts (likely a partial Bromcom export upstream).
"""

import json
import os
import re
import unicodedata
from datetime import datetime, timezone

import requests

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
DATA_REPO    = os.environ.get('DATA_REPO', 'wallscourtfarm/spelling-homelearning')
BRANCH       = 'main'
HEADERS      = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
BASE_URL     = f'https://api.github.com/repos/{DATA_REPO}/contents'

# Postgres roster on the WFA API since 25.09.26 (fed by Roster Import's Bromcom
# upload) — this used to read the shared-sync Google Apps Script, whose copy is
# no longer written by anything. Same pupil/class shape (compared field by field
# across all 383 pupils and 14 classes before switching). Fixed URLs, not
# environment overrides, so a stale Render setting can't quietly point it back
# at Google.
# The token comes from the HUB_TOKEN setting on the server, never from the code.
_HUB_TOKEN = os.environ.get('HUB_TOKEN', '')
ROSTER_URL  = 'https://api.wallscourt-farm-academy.co.uk/planning/pupilroster-db/pupils?token=' + _HUB_TOKEN
CLASSES_URL = 'https://api.wallscourt-farm-academy.co.uk/planning/pupilroster-db/classes?token=' + _HUB_TOKEN

ARCHIVE_PATH = 'data/archived/roster_leavers.json'
META_PATH    = 'data/roster_meta.json'

# Matches the class registry in data_manager.py
YEAR_GROUP_CLASSES = {
    '1': ['1ER', '1JS'],
    '2': ['2MY', '2JH'],
    '3': ['3JW', '3WU'],
    '4': ['4CC', '4RB'],
    '5': ['5LS', '5IM'],
    '6': ['6JM', '6SD'],
}
ALL_CLASSES = [c for classes in YEAR_GROUP_CLASSES.values() for c in classes]

MIN_ROSTER_RATIO = 0.8   # abort if roster < 80% of current pupils


def _norm(s):
    """Normalise a name for matching: strip accents, lowercase, collapse spaces."""
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', s).strip().lower()


def _cls_short(cls_id):
    return cls_id.lstrip('0123456789') if cls_id else cls_id


def _now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


# ── Roster fetch ──────────────────────────────────────────────────────────────

def fetch_roster():
    """Fetch the active pupil roster from the WFA API."""
    r = requests.get(ROSTER_URL, timeout=30)
    r.raise_for_status()
    data = r.json()
    pupils = data.get('pupils') if isinstance(data, dict) else data
    if not isinstance(pupils, list):
        raise ValueError('Roster endpoint returned unexpected payload')
    return pupils


def fetch_classes():
    """Fetch the hub's class list (code/display/teacherInitials). Non-fatal
    on failure — a stale teacher label is a much smaller problem than
    blocking the whole roster sync over it."""
    try:
        r = requests.get(CLASSES_URL, timeout=15)
        r.raise_for_status()
        data = r.json()
        classes = data.get('classes') if isinstance(data, dict) else data
        return classes if isinstance(classes, list) else []
    except Exception:
        return []


# ── GitHub I/O (fresh, uncached — sync writes need real shas) ────────────────

def _gh_get(path):
    import base64
    r = requests.get(f'{BASE_URL}/{path}', headers=HEADERS, timeout=15)
    if r.status_code == 200:
        fd = r.json()
        raw = base64.b64decode(fd.get('content') or '').decode('utf-8')
        return json.loads(raw), fd['sha']
    if r.status_code == 404:
        return None, None
    r.raise_for_status()


def _gh_put(path, obj, sha, message):
    import base64
    content = base64.b64encode(
        json.dumps(obj, indent=2, ensure_ascii=False).encode('utf-8')).decode('ascii')
    body = {'message': message, 'content': content, 'branch': BRANCH}
    if sha:
        body['sha'] = sha
    r = requests.put(f'{BASE_URL}/{path}', headers=HEADERS, timeout=20, json=body)
    return r.status_code in (200, 201)


# ── Sync ──────────────────────────────────────────────────────────────────────

def sync_roster(apply=True, remove_leavers=True, roster=None):
    """
    Merge the roster into every class file. Returns a summary dict.
    apply=False does the full match walk but writes nothing (dry run).
    """
    summary = {
        'ok': True, 'applied': apply, 'when': _now(),
        'roster_count': 0, 'updated': [], 'renamed': [], 'upn_attached': [],
        'added': [], 'removed': [], 'unmatched': [],
        'skipped_new': [], 'aborted': None,
    }

    try:
        pupils_roster = roster if roster is not None else fetch_roster()
    except Exception as e:
        summary['ok'] = False
        summary['aborted'] = f'Could not fetch roster: {e}'
        return summary

    summary['roster_count'] = len(pupils_roster)

    # Roster lookups
    by_upn, by_name = {}, {}
    roster_classes = set()
    for r in pupils_roster:
        upn = (r.get('upn') or r.get('id') or '').strip()
        if not upn:
            continue
        rec = {
            'upn': upn,
            'first': (r.get('first') or '').strip(),
            'last':  (r.get('last') or '').strip(),
            'class': (r.get('class') or '').strip(),
            'yearGroup': (r.get('yearGroup') or '').strip(),
            'pupil_id': (r.get('pupilId') or '').strip(),
        }
        by_upn[upn] = rec
        by_name.setdefault(_norm(f"{rec['first']} {rec['last']}"), rec)
        roster_classes.add(rec['class'])

    unknown_roster_classes = sorted(c for c in roster_classes if c not in ALL_CLASSES)

    # Load all class files (fresh shas)
    files = {}
    total_pupils = 0
    for cid in ALL_CLASSES:
        obj, sha = _gh_get(f'data/classes/{cid}.json')
        files[cid] = {'obj': obj or {'class_id': cid, 'pupils': []}, 'sha': sha,
                      'changed': False}
        total_pupils += len(files[cid]['obj'].get('pupils', []))

    # Refresh teacher_name/class_display from the hub (matched by display
    # name, since that's how class files are keyed here) — self-healing,
    # replaces the old manual "Class settings" editor.
    for hub_cls in fetch_classes():
        cid = str(hub_cls.get('display') or '').strip()
        f = files.get(cid)
        if not f:
            continue
        initials = str(hub_cls.get('teacherInitials') or '').strip()
        if initials and f['obj'].get('teacher') != initials:
            f['obj']['teacher'] = initials
            f['obj']['class_display'] = initials
            f['obj']['teacher_name'] = initials
            f['changed'] = True

    # Safety valve against partial exports upstream
    if total_pupils and len(by_upn) < MIN_ROSTER_RATIO * total_pupils:
        summary['ok'] = False
        summary['aborted'] = (
            f'Roster has {len(by_upn)} pupils but class files hold {total_pupils} — '
            f'below the {int(MIN_ROSTER_RATIO*100)}% safety threshold. Sync aborted; '
            'check the latest Bromcom import in the Pupil Tracker.')
        return summary

    # Existing UPN claims (any file) — stops one UPN being attached twice
    claimed = set()
    for f in files.values():
        for p in f['obj'].get('pupils', []):
            if p.get('upn'):
                claimed.add(p['upn'])

    # ── Match walk: refresh / rename / attach UPN / flag leavers ────────────
    leavers = []
    for cid in ALL_CLASSES:
        f = files[cid]
        kept = []
        for p in f['obj'].get('pupils', []):
            name = f"{p.get('first','')} {p.get('last','')}".strip()
            upn  = (p.get('upn') or '').strip()
            r    = by_upn.get(upn) if upn else None
            if r is None and not upn:
                cand = by_name.get(_norm(name))
                if cand and cand['upn'] not in claimed:
                    r = cand
            if r is not None:
                claimed.add(r['upn'])
                touched = False
                if not p.get('upn'):
                    p['upn'] = r['upn']
                    summary['upn_attached'].append({'cls': cid, 'name': name,
                                                    'upn': r['upn']})
                    touched = True
                if r['pupil_id'] and r['pupil_id'] != p.get('pupil_id'):
                    p['pupil_id'] = r['pupil_id']
                    touched = True
                if r['first'] and r['first'] != p.get('first'):
                    summary['renamed'].append({'cls': cid, 'id': p['id'],
                                               'was': name,
                                               'now': f"{r['first']} {r['last']}"})
                    p['first'] = r['first']
                    touched = True
                if r['last'] and r['last'] != p.get('last', ''):
                    if not (r['first'] and r['first'] != p.get('first')):
                        summary['renamed'].append({'cls': cid, 'id': p['id'],
                                                   'was': name,
                                                   'now': f"{p.get('first')} {r['last']}"})
                    p['last'] = r['last']
                    touched = True
                if r['class'] in ALL_CLASSES and p.get('cls') != _cls_short(r['class']):
                    p['cls'] = _cls_short(r['class'])
                    touched = True
                if touched:
                    f['changed'] = True
                    summary['updated'].append({'cls': cid, 'id': p['id']})
                kept.append(p)
            elif upn:
                # UPN'd pupil absent from roster → leaver
                if remove_leavers:
                    leavers.append({'cls': cid, 'pupil': p})
                    f['changed'] = True
                else:
                    summary['unmatched'].append(
                        {'cls': cid, 'name': name, 'upn': upn,
                         'note': 'on class file but not on roster (leaver removal off)'})
                    kept.append(p)
            else:
                # No UPN and no name match — never auto-removed, only reported
                summary['unmatched'].append(
                    {'cls': cid, 'name': name, 'upn': '',
                     'note': 'no UPN and no roster name match — left untouched'})
                kept.append(p)
        f['obj']['pupils'] = kept

    # Apply leaver removal now that flags are collected
    if leavers:
        leaver_by_cls = {}
        for item in leavers:
            leaver_by_cls.setdefault(item['cls'], set()).add(item['pupil']['id'])
        for cid, ids in leaver_by_cls.items():
            f = files[cid]
            before = len(f['obj']['pupils'])
            f['obj']['pupils'] = [p for p in f['obj']['pupils']
                                  if p['id'] not in ids]
            # Clear partner refs pointing at removed pupils (same file)
            for p in f['obj']['pupils']:
                if p.get('pair_id') in ids:
                    p['pair_id'] = ''
                    p['pair_colour'] = ''
            summary['removed'].extend(
                {'cls': cid, 'id': pid,
                 'name': next((f"{p['pupil'].get('first','')} {p['pupil'].get('last','')}".strip()
                               for p in leavers if p['pupil']['id'] == pid), pid),
                 'upn': next((p['pupil'].get('upn') for p in leavers
                              if p['pupil']['id'] == pid), '')}
                for pid in sorted(ids))
        # Cross-class partner refs
        leaver_ids = {item['pupil']['id'] for item in leavers}
        for cid in ALL_CLASSES:
            f = files[cid]
            for p in f['obj'].get('pupils', []):
                if p.get('pair_id') in leaver_ids:
                    p['pair_id'] = ''
                    p['pair_colour'] = ''
                    f['changed'] = True

    # ── New pupils from roster ───────────────────────────────────────────────
    max_n = 0
    for f in files.values():
        for p in f['obj'].get('pupils', []):
            pid = p.get('id', '')
            m = re.match(r'p(\d+)$', pid)
            if m:
                max_n = max(max_n, int(m.group(1)))

    for r in by_upn.values():
        if r['upn'] in claimed:
            continue
        cid = r['class']
        if cid not in ALL_CLASSES:
            summary['skipped_new'].append(
                {'name': f"{r['first']} {r['last']}", 'class': cid,
                 'note': 'class not in registry' if not unknown_roster_classes
                         else 'unknown class'})
            continue
        max_n += 1
        pid = f'p{max_n:02d}'
        new_pupil = {
            'id': pid,
            'first': r['first'],
            'last':  r['last'],
            'cls':   _cls_short(cid),
            'group': 'main',
            'tt_set': '2',
            'tt_mode': 'x',
            'table': '',
            'maths_level': 'standard',
            'reading_level': re.match(r'\d+', cid).group(0) if re.match(r'\d+', cid) else '5',
            'language': '',
            'pair_id': '',
            'pair_colour': '',
            # New pupils start at the very beginning of the whole list —
            # mastered=[] means no evidence they know anything yet.
            'word_pos': 0,
            'mastered': [],
            'rule_confidence': {},
            'us_code': '',
            'us_pin': '',
            'homophone_mastered': [],
            'homophone_history': {},
            'upn': r['upn'],
            'pupil_id': r['pupil_id'],
        }
        files[cid]['obj'].setdefault('pupils', []).append(new_pupil)
        files[cid]['changed'] = True
        claimed.add(r['upn'])
        summary['added'].append({'cls': cid, 'id': pid,
                                 'name': f"{r['first']} {r['last']}",
                                 'upn': r['upn']})

    # ── Write ────────────────────────────────────────────────────────────────
    if apply and summary['ok']:
        for cid in ALL_CLASSES:
            f = files[cid]
            if not f['changed'] or f['sha'] is None:
                continue
            n = len(f['obj'].get('pupils', []))
            if not _gh_put(f'data/classes/{cid}.json', f['obj'], f['sha'],
                           f'Roster sync ({summary["when"][:10]}): {cid} — '
                           f'+{len([a for a in summary["added"] if a["cls"]==cid])} '
                           f'-{len([r for r in summary["removed"] if r["cls"]==cid])} '
                           f'({n} pupils)'):
                summary['ok'] = False
                summary['aborted'] = f'Failed to commit {cid}'

        if summary['ok'] and summary['removed']:
            # Archive leavers to the private data repo before they disappear
            arch, arch_sha = _gh_get(ARCHIVE_PATH)
            arch = arch or []
            existing = {a.get('upn') for a in arch if a.get('upn')}
            for item in leavers:
                p = item['pupil']
                entry = {
                    'upn': p.get('upn', ''),
                    'id': p.get('id', ''),
                    'first': p.get('first', ''),
                    'last': p.get('last', ''),
                    'cls': p.get('cls', ''),
                    'removed_at': summary['when'],
                    'snapshot': p,
                }
                if not entry['upn'] or entry['upn'] not in existing:
                    arch.append(entry)
                    if entry['upn']:
                        existing.add(entry['upn'])
            arch = arch[-500:]    # keep the archive bounded
            if not _gh_put(ARCHIVE_PATH, arch, arch_sha,
                           f'Roster sync: archive {len(summary["removed"])} leaver(s)'):
                summary['ok'] = False
                summary['aborted'] = 'Failed to write leaver archive'

    # Deduplicate the removed report (leaver_by_cls loop can double-report)
    seen = set()
    deduped = []
    for r in summary['removed']:
        key = (r['cls'], r['id'])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    summary['removed'] = deduped

    # ── Meta for the status indicator ────────────────────────────────────────
    meta = {
        'last_sync': summary['when'],
        'ok': summary['ok'],
        'roster_count': summary['roster_count'],
        'source': 'bromcom via pupil roster database',
        'added': len(summary['added']),
        'removed': len(summary['removed']),
        'renamed': len(summary['renamed']),
        'upn_attached': len(summary['upn_attached']),
        'unmatched': len(summary['unmatched']),
        'applied': apply,
    }
    if apply:
        meta_obj, meta_sha = _gh_get(META_PATH)
        if not _gh_put(META_PATH, meta, meta_sha, f'Roster sync meta {summary["when"]}'):
            meta['write_failed'] = True
    summary['meta'] = meta
    return summary


# ── Pupil codes (pupil_id) ────────────────────────────────────────────────────

ATTACH_MESSAGE = 'Add pupil codes (no other change)'
_ATTACH_RETRIES = 3


def _plan_pupil_ids(pupils, by_upn):
    """Work out the pupil_id changes for one class file's pupils.
    Match is by UPN, exact, never by name. Returns (changes, skipped) where
    changes is {pupil index: new pupil_id} and skipped is a list of
    (pupil index, reason). Pure: does not modify `pupils`."""
    changes, skipped, unchanged = {}, [], 0
    for i, p in enumerate(pupils):
        upn = (p.get('upn') or '').strip()
        if not upn:
            skipped.append((i, 'no UPN'))
            continue
        rec = by_upn.get(upn)
        if rec is None:
            skipped.append((i, 'not on roster'))
            continue
        if not rec['pupil_id']:
            skipped.append((i, 'roster has no pupil code'))
            continue
        if p.get('pupil_id') == rec['pupil_id']:
            unchanged += 1
        else:
            changes[i] = rec['pupil_id']
    return changes, skipped, unchanged


def _apply_pupil_ids(obj, by_upn):
    """Set pupil_id (and nothing else) on the pupils of `obj` that need it.
    Returns the number of pupils changed. Re-matches by UPN every time, so it
    is safe to run again on a freshly re-read copy."""
    changes, _, _ = _plan_pupil_ids(obj.get('pupils', []), by_upn)
    for i, pid in changes.items():
        obj['pupils'][i]['pupil_id'] = pid
    return len(changes)


def attach_pupil_ids(dry_run=True, roster=None):
    """Add/refresh `pupil_id` on every pupil in every class file, matching the
    roster by UPN only. Touches no other field. Pupils with no UPN, no roster
    match or no roster pupil code are left alone and reported by initials
    label only (never names).

    dry_run=True (default) reads and counts but writes nothing. A real run
    writes one commit per changed class file; each write re-reads the file
    and retries if GitHub reports a stale sha, so a concurrent edit is never
    overwritten.
    """
    report = {'ok': True, 'dry_run': bool(dry_run), 'when': _now(),
              'roster_count': 0, 'classes_checked': 0, 'pupils_checked': 0,
              'to_add': 0, 'already_set': 0, 'added': 0,
              'files_changed': 0, 'files_failed': [],
              'skipped_count': 0, 'skipped': [], 'error': None}

    try:
        pupils_roster = roster if roster is not None else fetch_roster()
    except Exception as e:
        # Deliberately not str(e): request errors can contain the roster URL.
        report['ok'] = False
        report['error'] = f'Could not fetch roster ({type(e).__name__})'
        return report

    by_upn = {}
    for r in pupils_roster:
        upn = (r.get('upn') or r.get('id') or '').strip()
        if upn:
            by_upn[upn] = {'pupil_id': (r.get('pupilId') or '').strip()}
    report['roster_count'] = len(by_upn)

    # Read every class first (fresh) so labels are worked out school-wide,
    # the same way Class Manager does it.
    files = {}
    for cid in ALL_CLASSES:
        obj, sha = _gh_get(f'data/classes/{cid}.json')
        if obj is None:
            continue
        files[cid] = (obj, sha)
    report['classes_checked'] = len(files)

    from names_display import label_list
    flat = [(cid, i, p) for cid, (obj, _) in files.items()
            for i, p in enumerate(obj.get('pupils', []))]
    labels = label_list([(p.get('first', ''), p.get('last', '')) for _, _, p in flat])
    label_of = {(cid, i): labels[n] for n, (cid, i, _) in enumerate(flat)}
    report['pupils_checked'] = len(flat)

    for cid, (obj, sha) in files.items():
        changes, skipped, unchanged = _plan_pupil_ids(obj.get('pupils', []), by_upn)
        report['already_set'] += unchanged
        report['to_add'] += len(changes)
        for i, reason in skipped:
            report['skipped'].append({'cls': cid, 'label': label_of[(cid, i)],
                                      'reason': reason})
        if dry_run or not changes:
            continue
        if sha is None:
            report['files_failed'].append(cid)
            continue

        path = f'data/classes/{cid}.json'
        cur, cur_sha, written = obj, sha, 0
        for attempt in range(_ATTACH_RETRIES):
            n = _apply_pupil_ids(cur, by_upn)
            if n == 0:
                written = 0
                ok = True
                break
            ok = _gh_put(path, cur, cur_sha, ATTACH_MESSAGE)
            if ok:
                written = n
                break
            # Stale sha (someone saved in between) or a failed write:
            # re-read the latest copy and re-apply onto it.
            fresh, fresh_sha = _gh_get(path)
            if fresh is None or fresh_sha is None:
                break
            cur, cur_sha = fresh, fresh_sha
        else:
            ok = False
        if ok:
            if written:
                report['added'] += written
                report['files_changed'] += 1
        else:
            report['files_failed'].append(cid)

    report['skipped_count'] = len(report['skipped'])
    if report['files_failed']:
        report['ok'] = False
        report['error'] = 'Some class files could not be saved: ' + ', '.join(report['files_failed'])
    if not dry_run:
        try:
            import data_manager
            for cid in files:
                data_manager._invalidate(f'data/classes/{cid}.json')
        except Exception:
            pass
    return report


if __name__ == '__main__':
    import sys
    result = sync_roster(apply='--apply' in sys.argv)
    print(json.dumps({k: v for k, v in result.items() if k != 'meta'}, indent=1))
    print('meta:', json.dumps(result.get('meta'), indent=1))
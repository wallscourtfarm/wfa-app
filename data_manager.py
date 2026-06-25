"""
data_manager.py — WFA Flask app data layer
Data lives in wallscourtfarm/spelling-homelearning GitHub repo.
"""
import os, json, base64, requests, time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from word_bank import WORD_BANK, get_active_words, mastery_stats

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
DATA_REPO    = os.environ.get('DATA_REPO', 'wallscourtfarm/spelling-homelearning')
BRANCH       = 'main'
HEADERS      = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
BASE_URL     = f'https://api.github.com/repos/{DATA_REPO}/contents'

TT_ORDER   = ['2','5','4','8','3','6','9','7','11','12','All']

# ── Class registry ─────────────────────────────────────────────────────────────
# Single source of truth. Class IDs are permanent stable identifiers — teacher
# labels are stored in the JSON and can be changed without renaming anything.

YEAR_GROUP_CLASSES = {
    '1': ['Y1_ET', 'Y1_ER'],
    '2': ['Y2_JH', 'Y2_MY'],
    '3': ['Y3_RB', 'Y3_JW'],
    '4': ['Y4_IM', 'Y4_WU'],
    '5': ['Y5_CK', 'Y5_LE'],
    '6': ['Y6_JM', 'Y6_SD'],
}

ALL_CLASSES = [c for classes in YEAR_GROUP_CLASSES.values() for c in classes]

YEAR_WORD_ZONE = {
    '1': 21, '2': 78, '3': 131, '4': 185, '5': 239, '6': 290,
}

def get_year_group(class_id):
    """Return year group string ('1'–'6') for a class_id, or None."""
    for yr, classes in YEAR_GROUP_CLASSES.items():
        if class_id in classes:
            return yr
    if class_id and '_all' in class_id:
        return class_id[1]
    return None

def _resolve_classes(class_id):
    """
    Return list of real class IDs to load.
      'Y4_all' -> ['Y4_IM', 'Y4_WU']
      'Y4_IM'  -> ['Y4_IM']
      'all'    -> ['Y4_IM', 'Y4_WU']  (legacy Y4 fallback)
    """
    if class_id == 'all':
        return list(YEAR_GROUP_CLASSES.get('4', []))
    if class_id and class_id.endswith('_all'):
        yr = class_id[1]
        return list(YEAR_GROUP_CLASSES.get(yr, []))
    return [class_id] if class_id else []

def get_ref_class(class_id):
    """Single real class ID for config lookups when an _all selector is used."""
    classes = _resolve_classes(class_id)
    return classes[0] if classes else 'Y4_IM'

def get_class_options(include_all_per_year=True):
    """
    Flat list of (value, label) tuples for all year groups.
    All routes import this — no local CLASS_OPTIONS definitions.
    """
    options = []
    for yr, classes in YEAR_GROUP_CLASSES.items():
        if include_all_per_year:
            options.append((f'Y{yr}_all', f'Y{yr} \u2014 All'))
        for cid in classes:
            suffix = cid.split('_')[1]
            options.append((cid, f'Y{yr} \u2014 {suffix}'))
    return options

# ── In-process TTL cache ──────────────────────────────────────────────────────
_CACHE     = {}   # path -> (data, sha, expires_at)
_CACHE_TTL = 90   # seconds

def _invalidate(path):
    _CACHE.pop(path, None)

# ── GitHub I/O ────────────────────────────────────────────────────────────────

def _get_file(path):
    now = time.time()
    if path in _CACHE:
        cached_data, cached_sha, expires = _CACHE[path]
        if now < expires:
            return cached_data, cached_sha
    r = requests.get(f'{BASE_URL}/{path}', headers=HEADERS, timeout=10)
    if r.status_code == 200:
        d = r.json()
        data = json.loads(base64.b64decode(d['content']).decode('utf-8'))
        sha  = d['sha']
        _CACHE[path] = (data, sha, now + _CACHE_TTL)
        return data, sha
    return None, None

def _put_file(path, data, sha, message):
    content = base64.b64encode(
        json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
    ).decode('utf-8')
    r = requests.put(f'{BASE_URL}/{path}', headers=HEADERS,
                     json={'message':message,'content':content,'sha':sha,'branch':BRANCH}, timeout=15)
    if r.status_code in (200, 201):
        _invalidate(path)   # evict stale entry after a write
        return True
    return False

def _load_classes_parallel(class_ids):
    """Fetch multiple class files concurrently; returns {cid: data_or_None}."""
    if len(class_ids) <= 1:
        return {cid: load_class(cid) for cid in class_ids}
    results = {}
    with ThreadPoolExecutor(max_workers=len(class_ids)) as ex:
        futures = {ex.submit(load_class, cid): cid for cid in class_ids}
        for f in as_completed(futures):
            results[futures[f]] = f.result()
    return results

# ── TT helpers ────────────────────────────────────────────────────────────────

def advance_tt(tt_set, tt_mode='x'):
    if str(tt_set) == 'All' and tt_mode == 'xd': return ('All','xd')
    if tt_mode != 'xd': return (tt_set,'xd')
    try:
        i = TT_ORDER.index(str(tt_set))
        new_set = TT_ORDER[i+1] if i+1 < len(TT_ORDER) else tt_set
    except ValueError:
        new_set = tt_set
    return (new_set,'x')

def tt_label(tt_set, tt_mode):
    return f'{tt_set}{"×÷" if tt_mode=="xd" else "×"}'

# ── Class loading ─────────────────────────────────────────────────────────────

def load_class(class_id):
    data, _ = _get_file(f'data/classes/{class_id}.json')
    return data

def load_weekly_config():
    data, _ = _get_file('data/weekly_config.json')
    return data or {}

def get_rule(rule_id_str):
    """Return a rule tuple [stage, step, title, words, ...] by ID string like '4-2' or '0-3'."""
    if not rule_id_str: return None
    try:
        stage, step = int(rule_id_str.split('-')[0]), int(rule_id_str.split('-')[1])
        if stage == 0:
            # Custom rule — look up in custom_rules.json
            data, _ = _get_file('data/custom_rules.json')
            if data:
                rules_list = data if isinstance(data, list) else data.get('rules', [])
                for cr in rules_list:
                    if cr.get('id') == step or cr.get('id') == rule_id_str:
                        return [0, cr.get('id', step), cr.get('title', ''), cr.get('words', [])]
        from spelling_rules import SPELLING_RULES
        for r in SPELLING_RULES:
            if r[0]==stage and r[1]==step: return r
    except Exception: pass
    return None

# ── Dashboard ─────────────────────────────────────────────────────────────────

def _pupil_row(p):
    m = set(p.get('mastered', []))
    s = mastery_stats(m)
    ts, tm = p.get('tt_set','2'), p.get('tt_mode','x')
    return {
        'id':        p.get('id',''),
        'first':     p.get('first',''),
        'last':      p.get('last',''),
        'group':     p.get('group','main'),
        'cls':       p.get('cls',''),
        'tt':        tt_label(ts, tm),
        'tt_set':    ts,
        # Full stats — template picks the right ones for the active year
        'y1_pct':    s.get('Y1',0),
        'y2_pct':    s.get('Y2',0),
        'y3_pct':    s.get('Y3',0),
        'y4_pct':    s.get('Y4',0),
        'y5_pct':    s.get('Y5',0),
        'y6_pct':    s.get('Y6',0),
        'ks1_pct':   s.get('KS1',0),
        'lks2_pct':  s.get('LKS2',0),
        'uks2_pct':  s.get('UKS2',0),
        'ks2_pct':   s.get('KS2',0),
        'all_pct':   s.get('total',0),
    }

def load_dashboard(class_id='Y4_all'):
    class_ids = _resolve_classes(class_id)
    class_data = _load_classes_parallel(class_ids)
    all_pupils = []
    for cid in class_ids:
        d = class_data.get(cid)
        if d: all_pupils.extend(d.get('pupils', []))
    if not all_pupils and class_id not in ('all',) and not class_id.endswith('_all'):
        return None

    rows     = [_pupil_row(p) for p in all_pupils]
    tt_dist  = {t: sum(1 for p in all_pupils if p.get('tt_set')==t) for t in TT_ORDER}
    stats    = {
        'total':        len(all_pupils),
        'main':         sum(1 for p in all_pupils if p.get('group','main')=='main'),
        'revision':     sum(1 for p in all_pupils if p.get('group')=='revision'),
        'paired':       sum(1 for p in all_pupils if p.get('pair_id')),
        'avg_mastered': sum(len(p.get('mastered',[])) for p in all_pupils) // max(len(all_pupils),1),
    }
    return {'rows': rows, 'tt_dist': tt_dist, 'stats': stats}

# ── Lowest Confidence Key Spellings ───────────────────────────────────────────────

def lowest_confidence_key_spellings(class_id='Y4_all', year=None, top_n=10):
    """Return top_n Key Spelling words most commonly unmastered across pupils.
    Includes the current year group AND all prior years (Key Spellings only),
    so gaps from earlier years surface alongside current-year words.
    """
    class_ids = _resolve_classes(class_id)
    class_data = _load_classes_parallel(class_ids)
    all_pupils = []
    for cid in class_ids:
        d = class_data.get(cid)
        if d: all_pupils.extend(d.get('pupils', []))
    if not all_pupils:
        return []
    # Build set of years to include: current year and all prior years with Key Spellings
    YEAR_ORDER = ['3', '4', '5', '6']  # Key Spellings start at Y3
    if year and year in YEAR_ORDER:
        include_years = set(YEAR_ORDER[:YEAR_ORDER.index(year) + 1])
    else:
        include_years = None  # no filter — include all
    key_words = [w for w, yr, ks, phase, label in WORD_BANK
                 if label == 'Key Spelling' and (include_years is None or yr in include_years)]
    if not key_words:
        return []
    total = len(all_pupils)
    counts = {}
    for word in key_words:
        wl = word.lower()
        counts[wl] = sum(1 for p in all_pupils if wl not in {m.lower() for m in p.get('mastered', [])})
    sorted_words = sorted(counts.items(), key=lambda x: -x[1])[:top_n]
    return [{'word': w, 'unmastered': c, 'total': total,
             'pct': round(c / total * 100) if total else 0}
            for w, c in sorted_words]

# ── TT Check ─────────────────────────────────────────────────────────────────

def load_tt_pupils(class_id='Y4_IM'):
    data = load_class(class_id)
    if not data: return []
    result = []
    for p in data.get('pupils',[]):
        ts, tm = p.get('tt_set','2'), p.get('tt_mode','x')
        name = p.get('first','?')
        if p.get('last'): name = f"{name} {p['last']}"
        result.append({'id':p['id'],'name':name,'first':p.get('first',''),
                       'tt_set':ts,'tt_mode':tm,'label':tt_label(ts,tm)})
    def key(p):
        try: idx = TT_ORDER.index(str(p['tt_set']))
        except ValueError: idx=99
        return (idx, 1 if p['tt_mode']=='xd' else 0, p['name'].lower())
    return sorted(result, key=key)

def advance_tt_pupils(class_id, pupil_ids):
    path = f'data/classes/{class_id}.json'
    data, sha = _get_file(path)
    if not data: return {'ok':False,'error':f'Could not load {path}'}
    id_set, changed = set(pupil_ids), 0
    for i,p in enumerate(data.get('pupils',[])):
        if p['id'] in id_set:
            ns,nm = advance_tt(p.get('tt_set','2'), p.get('tt_mode','x'))
            data['pupils'][i]['tt_set']=ns; data['pupils'][i]['tt_mode']=nm; changed+=1
    if changed and not _put_file(path,data,sha,f'TT advance: {class_id} ({changed} pupils)'):
        return {'ok':False,'error':'GitHub write failed'}
    return {'ok':True,'count':changed}

# ── Spelling Bee ──────────────────────────────────────────────────────────────

def load_bee_pupils(class_id='Y4_IM'):
    data = load_class(class_id)
    wc   = load_weekly_config()
    cfg  = wc.get('classes',{}).get(class_id,{})
    main_rule = get_rule(cfg.get('main_rule_id',''))
    rev_rule  = get_rule(cfg.get('revision_rule_id',''))
    if not data: return [], {}, ''
    pupils = []
    for p in data.get('pupils',[]):
        mastered = set(p.get('mastered',[]))
        words    = get_active_words(p.get('word_pos',0), mastered, 5)
        is_rev   = p.get('group')=='revision'
        rule     = rev_rule if is_rev else main_rule
        pupils.append({'id':p['id'],'first':p.get('first',''),'cls':p.get('cls',''),'file_cls':class_id,
                       'group':p.get('group','main'),'is_rev':is_rev,
                       'rule_label': rule[2] if rule else ('Revision' if is_rev else 'Main'),
                       'words': words,
                       'words_updated_at': p.get('words_updated_at','')})
    rules_info = {
        'main':     main_rule[2] if main_rule else '—',
        'revision': rev_rule[2]  if rev_rule  else '—',
        'week':     wc.get('week_ref',''),
    }
    return pupils, rules_info, wc.get('week_ref','')

def _apply_assessment(pupil, correct_words):
    p = dict(pupil)
    mastered = set(p.get('mastered',[]))
    mastered.update(correct_words)
    p['mastered'] = sorted(mastered)
    return p

def save_bee_assessment(class_id, assessments):
    path = f'data/classes/{class_id}.json'
    data, sha = _get_file(path)
    if not data: return {'ok':False,'error':f'Could not load {path}'}
    ass_map, saved = {a['pupil_id']:a for a in assessments}, 0
    for i,p in enumerate(data.get('pupils',[])):
        entry = ass_map.get(p['id'])
        if not entry: continue
        words = entry.get('words',[])
        if words:
            updated = _apply_assessment(p, words)
            updated['words_updated_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            data['pupils'][i] = updated; saved+=1
    if saved and not _put_file(path,data,sha,f'Spelling Bee: {class_id} ({saved} pupils)'):
        return {'ok':False,'error':'GitHub write failed'}
    return {'ok':True,'saved':saved}

# ── Learners ──────────────────────────────────────────────────────────────────

def load_learners(class_id='Y4_all'):
    # Resolve the target classes
    target_ids = _resolve_classes(class_id)
    # Partner lookup: same year group only (partners are always within a year)
    yr = class_id[1] if len(class_id) > 1 and class_id[0] == 'Y' else '4'
    yr_class_ids = list(YEAR_GROUP_CLASSES.get(yr, target_ids))
    all_ids = list(dict.fromkeys(yr_class_ids + target_ids))  # deduplicated
    class_data = _load_classes_parallel(all_ids)

    partner_map = {}
    for cid in yr_class_ids:
        d = class_data.get(cid)
        if d:
            for p in d.get('pupils', []):
                partner_map[p['id']] = p.get('first') or '?'

    pupils = []
    for cid in target_ids:
        d = class_data.get(cid)
        if d:
            pupils.extend(d.get('pupils', []))

    return [{**p, 'partner_name': partner_map.get(p.get('pair_id',''), '—')
             if p.get('pair_id') else '—'} for p in pupils]

def save_weekly_config(data):
    """Save weekly_config.json back to GitHub."""
    _, sha = _get_file('data/weekly_config.json')
    if sha is None:
        return False
    return _put_file('data/weekly_config.json', data, sha, 'Update weekly config')


def list_plannable_rules():
    """All plannable rules (standard + custom) for Settings dropdowns."""
    from spelling_rules import SPELLING_RULES
    custom_rules = load_custom_rules()
    custom   = [(f'0-{cr["id"]}', f'Custom: {cr["title"]}') for cr in custom_rules]
    standard = [(f'{r[0]}-{r[1]}', f'S{r[0]} Step {r[1]}: {r[2]}')
                for r in SPELLING_RULES if r[4] == 0]
    return custom + standard

# ── Custom Rules ──────────────────────────────────────────────────────────────

def _put_file_create(path, data, message):
    """Create a new file (no sha needed)."""
    content = base64.b64encode(
        json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
    ).decode('utf-8')
    r = requests.put(f'{BASE_URL}/{path}', headers=HEADERS,
                     json={'message': message, 'content': content, 'branch': BRANCH}, timeout=15)
    return r.status_code in (200, 201)

def load_custom_rules():
    """Return list of custom rule dicts, or [] if file missing."""
    data, _ = _get_file('data/custom_rules.json')
    if not data:
        return []
    return data.get('rules', [])

def save_custom_rules(rules, next_id):
    """Save custom rules back to GitHub. Creates file if it doesn't exist."""
    path = 'data/custom_rules.json'
    data = {'next_id': next_id, 'rules': rules}
    _, sha = _get_file(path)
    if sha is None:
        return _put_file_create(path, data, 'Create custom_rules.json')
    return _put_file(path, data, sha, 'Update custom rules')

def load_rule_confidence():
    """Return dict of rule_id -> {level: 0-3}. 0=unset."""
    data, _ = _get_file('data/rule_confidence.json')
    return data or {}

def save_rule_confidence(confidence):
    """Save rule confidence dict back to GitHub."""
    path = 'data/rule_confidence.json'
    _, sha = _get_file(path)
    if sha is None:
        return _put_file_create(path, confidence, 'Create rule_confidence.json')
    return _put_file(path, confidence, sha, 'Update rule confidence')

# ── Bee → rule confidence ─────────────────────────────────────────────────────

def update_rule_confidence_from_bee(assessments):
    """
    Given a list of {pupil_id, words, confident} dicts from a Bee save,
    tally confident responses per rule and update rule_confidence.json.

    Proportion thresholds: <40% → Low (1), 40–70% → Medium (2), >70% → High (3).
    Only rules that had at least one pupil assessed are updated — rules with no
    data this session are left unchanged so manual settings are preserved.
    """
    if not assessments:
        return False

    # Build pupil_id → group map across all classes
    pupil_group = {}
    for cid in ALL_CLASSES:
        d = load_class(cid)
        if d:
            for p in d.get('pupils', []):
                pupil_group[p['id']] = p.get('group', 'main')

    wc = load_weekly_config()
    cls_cfg = wc.get('classes', {})
    # All classes share the same rules, so just take the first
    any_cfg = next(iter(cls_cfg.values()), {}) if cls_cfg else {}
    main_rule_id = any_cfg.get('main_rule_id', '')
    rev_rule_id  = any_cfg.get('revision_rule_id', '')

    # Tally per rule: {rule_id: [total, confident_count]}
    tally = {}
    for a in assessments:
        pid       = a.get('pupil_id', '')
        confident = bool(a.get('confident', False))
        group     = pupil_group.get(pid, 'main')
        rule_id   = rev_rule_id if group == 'revision' else main_rule_id
        if not rule_id:
            continue
        if rule_id not in tally:
            tally[rule_id] = [0, 0]
        tally[rule_id][0] += 1
        if confident:
            tally[rule_id][1] += 1

    if not tally:
        return False

    # Convert tally to confidence level
    def _level(total, conf_count):
        if total == 0:
            return 0
        pct = conf_count / total
        if pct > 0.70:
            return 3  # High
        if pct >= 0.40:
            return 2  # Medium
        return 1      # Low

    conf = load_rule_confidence()
    for rule_id, (total, conf_count) in tally.items():
        conf[rule_id] = {'level': _level(total, conf_count)}

    return save_rule_confidence(conf)


def load_term_dates():
    """Load term weeks from data/term_dates.json.
    Returns list of {label, iso, display, term, week} dicts, or [] on failure."""
    content, _ = _get_file("data/term_dates.json")
    return content or []


def term_dates_by_term(term_dates):
    """Group term_dates list into OrderedDict keyed by term number string.
    e.g. {'1': [{label:'T1W1', ...}, ...], '2': [...], ...}"""
    from collections import OrderedDict
    grouped = OrderedDict()
    for w in term_dates:
        t = str(w.get('term', ''))
        if t not in grouped:
            grouped[t] = []
        grouped[t].append(w)
    return grouped


# ── Class file write helpers ───────────────────────────────────────────────────

def save_class(class_id, data, message='Update class'):
    """Write a class JSON back to GitHub. Creates file if it does not exist."""
    path = f'data/classes/{class_id}.json'
    _, sha = _get_file(path)
    if sha is None:
        return _put_file_create(path, data, message)
    return _put_file(path, data, sha, message)


# ── Teacher label update ───────────────────────────────────────────────────────

def update_teacher_label(class_id, teacher_code, teacher_name=''):
    """
    Update the teacher label fields in a class JSON.
    The class_id (filename) never changes — only the display fields do.
    teacher_code: short initials shown in UI (e.g. 'IM')
    teacher_name: optional full name (e.g. 'Mr McLean')
    """
    path = f'data/classes/{class_id}.json'
    data, sha = _get_file(path)
    if not data:
        return {'ok': False, 'error': f'Class {class_id} not found'}
    data['teacher']       = teacher_code
    data['class_display'] = teacher_code
    if teacher_name:
        data['teacher_name'] = teacher_name
    elif 'teacher_name' not in data:
        data['teacher_name'] = teacher_code
    ok = _put_file(path, data, sha, f'Update teacher label: {class_id} -> {teacher_code}')
    return {'ok': ok}


# ── CSV bulk import ────────────────────────────────────────────────────────────

def bulk_import_pupils(class_id, csv_text):
    """
    Import pupils from CSV text into a class.
    CSV format (header optional): first, last
    Pupils start at the correct word_pos for their year group.
    Returns {'ok': True, 'imported': n, 'errors': [...]}
    """
    import csv, io
    path = f'data/classes/{class_id}.json'
    data, sha = _get_file(path)
    if not data:
        return {'ok': False, 'error': f'Class {class_id} not found'}

    yr        = get_year_group(class_id) or '4'
    start_pos = YEAR_WORD_ZONE.get(yr, 185)
    suffix    = class_id.split('_')[1]

    existing_ids = {p['id'] for p in data.get('pupils', [])}
    max_n = 0
    for pid in existing_ids:
        try: max_n = max(max_n, int(pid[1:]))
        except: pass
    next_n = max_n + 1

    reader   = csv.reader(io.StringIO(csv_text.strip()))
    imported, errors = 0, []

    for i, row in enumerate(reader):
        if not row: continue
        if i == 0 and row[0].strip().lower() in ('first', 'firstname', 'name', 'forename'):
            continue
        first = row[0].strip().title() if len(row) > 0 else ''
        last  = row[1].strip().title() if len(row) > 1 else ''
        if not first:
            errors.append(f'Row {i+1}: no first name — skipped')
            continue

        pid = f'p{next_n:02d}'
        while pid in existing_ids:
            next_n += 1
            pid = f'p{next_n:02d}'

        data['pupils'].append({
            'id':               pid,
            'first':            first,
            'last':             last,
            'cls':              suffix,
            'group':            'main',
            'tt_set':           '2',
            'tt_mode':          'x',
            'table':            '',
            'adapted_hl':       False,
            'pair_id':          '',
            'pair_colour':      '',
            'word_pos':         start_pos,
            'mastered':         [],
            'rule_confidence':  {},
            'homophone_mastered': [],
            'homophone_history':  {},
            'ss_user':          '',
            'ss_pass':          '',
        })
        existing_ids.add(pid)
        next_n += 1
        imported += 1

    if imported:
        ok = _put_file(path, data, sha, f'Bulk import: {imported} pupils into {class_id}')
        if not ok:
            return {'ok': False, 'error': 'GitHub write failed'}

    return {'ok': True, 'imported': imported, 'errors': errors}


# ── Year-end rollover ──────────────────────────────────────────────────────────

def year_end_rollover(year_group):
    """
    Move all pupils in year_group up by one year.
    Y6 pupils are archived (data/archive/Y6_rollover.json) and removed.
    Y1–Y5 pupils land in the first class of the next year with cls='' (pending
    teacher reassignment via class manager).

    Returns {'ok': True, 'moved': n, 'archived': n} or {'ok': False, 'error': ...}
    """
    import datetime
    yr   = str(year_group)
    classes = YEAR_GROUP_CLASSES.get(yr)
    if not classes:
        return {'ok': False, 'error': f'No classes registered for year {yr}'}

    # Collect all pupils from every class in this year group
    all_pupils, source_snapshots = [], []
    for cid in classes:
        path = f'data/classes/{cid}.json'
        data, sha = _get_file(path)
        if not data:
            continue
        all_pupils.extend(data.get('pupils', []))
        source_snapshots.append((path, data, sha))

    moved = archived = 0

    if yr == '6':
        # Archive Y6 — write to archive file, then clear source classes
        stamp       = datetime.date.today().isoformat()
        archive_path = f'data/archive/Y6_rollover_{stamp}.json'
        archive_data = {
            'archived_date': stamp,
            'year': '6',
            'count': len(all_pupils),
            'pupils': all_pupils,
        }
        _put_file_create(archive_path, archive_data,
                         f'Archive Y6 ({len(all_pupils)} pupils, {stamp})')
        archived = len(all_pupils)
        for path, data, sha in source_snapshots:
            data['pupils'] = []
            _put_file(path, data, sha, f'Year-end rollover: clear {path}')
        return {'ok': True, 'moved': 0, 'archived': archived}

    # Y1–Y5: move pupils to first class of next year group
    next_yr      = str(int(yr) + 1)
    next_classes = YEAR_GROUP_CLASSES.get(next_yr)
    if not next_classes:
        return {'ok': False, 'error': f'No classes registered for year {next_yr}'}

    target_id   = next_classes[0]
    target_path = f'data/classes/{target_id}.json'
    target_data, target_sha = _get_file(target_path)
    if not target_data:
        return {'ok': False, 'error': f'Could not load target class {target_id}'}

    # Update each pupil: clear cls (unassigned) and update word_pos floor
    next_zone = YEAR_WORD_ZONE.get(next_yr, 0)
    for p in all_pupils:
        p['cls']     = ''    # pending — teacher reassigns via class manager
        p['pending'] = True  # flag for class manager to surface in Pending view
        if p.get('word_pos', 0) < next_zone:
            p['word_pos'] = next_zone

    target_data.setdefault('pupils', []).extend(all_pupils)
    moved = len(all_pupils)
    ok = _put_file(target_path, target_data, target_sha,
                   f'Year-end rollover: Y{yr}->Y{next_yr} ({moved} pupils)')
    if not ok:
        return {'ok': False, 'error': 'Failed to write to target class'}

    # Clear source classes
    for path, data, sha in source_snapshots:
        data['pupils'] = []
        _put_file(path, data, sha, f'Year-end rollover: clear {path}')

    return {'ok': True, 'moved': moved, 'archived': 0}


# ── Year group pupil counts ────────────────────────────────────────────────────

def get_year_counts():
    """
    Return dict of year_group -> {total, pending, classes: [{id, display, count}]}
    Used by the rollover page to show current state before acting.
    """
    result = {}
    for yr, classes in YEAR_GROUP_CLASSES.items():
        yr_total, yr_pending = 0, 0
        cls_info = []
        for cid in classes:
            d = load_class(cid)
            pupils  = d.get('pupils', []) if d else []
            count   = len(pupils)
            pending = sum(1 for p in pupils if p.get('pending'))
            yr_total   += count
            yr_pending += pending
            cls_info.append({
                'id':      cid,
                'display': d.get('class_display', cid.split('_')[1]) if d else cid.split('_')[1],
                'teacher': d.get('teacher_name', d.get('teacher', '')) if d else '',
                'count':   count,
                'pending': pending,
            })
        result[yr] = {
            'total':   yr_total,
            'pending': yr_pending,
            'classes': cls_info,
        }
    return result


def get_class_options_for_year(yr, include_all=True):
    """
    Class options filtered to a single year group — used by all routes so the
    dropdown only shows the active year's classes.
    """
    yr      = str(yr)
    classes = YEAR_GROUP_CLASSES.get(yr, [])
    options = []
    if include_all:
        options.append((f'Y{yr}_all', f'Y{yr} \u2014 All'))
    for cid in classes:
        suffix = cid.split('_')[1]
        options.append((cid, f'Y{yr} \u2014 {suffix}'))
    return options


# ── Mastery import ─────────────────────────────────────────────────────────────

def import_pupils_with_mastery(year_group, csv_text, on_conflict='merge'):
    """
    Import pupils with mastered word lists.  Accepts two CSV formats:

    FORMAT A — single Mastered column (space/comma separated words):
      First, Last, Class, Mastered
      Asel, Acar, IM, "about accident address"

    FORMAT B — wide format (one column per word, 1 = mastered):
      First, Last, Class, about, accident, address, ...
      Asel, Acar, IM, 1, 1, 1, ...

    Format is auto-detected from the header row.
    on_conflict: 'merge' (union) or 'replace' (overwrite).
    """
    import csv, io
    from word_bank import WORD_BANK

    yr      = str(year_group)
    classes = YEAR_GROUP_CLASSES.get(yr, [])
    cls_map = {cid.split('_')[1].upper(): cid for cid in classes}
    bank_words = {w[0] for w in WORD_BANK}

    # Strip BOM if present
    csv_text = csv_text.lstrip('\ufeff').lstrip('\xef\xbb\xbf')

    reader = csv.reader(io.StringIO(csv_text.strip()))
    raw_headers = next(reader, None)
    if not raw_headers:
        return {'ok': False, 'error': 'Empty CSV'}

    # Normalise header names
    headers = [h.strip() for h in raw_headers]
    h_lower = [h.lower() for h in headers]

    # Detect format
    has_mastered_col = 'mastered' in h_lower
    # Ensure at minimum First, Last, Class exist
    for req in ('first', 'last', 'class'):
        if req not in h_lower:
            return {'ok': False, 'error': f'Missing required column: {req}'}

    rows     = list(reader)
    warnings = []

    if has_mastered_col:
        # FORMAT A — single Mastered column
        fi = h_lower.index('first')
        li = h_lower.index('last')
        ci = h_lower.index('class')
        mi = h_lower.index('mastered')

        def parse_row_mastered(row):
            raw = row[mi].strip() if mi < len(row) else ''
            if ',' in raw:
                return {w.strip() for w in raw.split(',') if w.strip()}
            return {w.strip() for w in raw.split() if w.strip()}

        def get_fields(row):
            return (row[fi].strip().title() if fi < len(row) else '',
                    row[li].strip().title() if li < len(row) else '',
                    row[ci].strip().upper() if ci < len(row) else '')

    else:
        # FORMAT B — wide (one column per word)
        fi = h_lower.index('first')
        li = h_lower.index('last')
        ci = h_lower.index('class')
        # Remaining columns are word names
        word_cols = [(i, headers[i]) for i in range(len(headers)) if i not in (fi, li, ci)]
        unknown_words = {w for _, w in word_cols if w not in bank_words}
        if unknown_words:
            warnings.append(f'{len(unknown_words)} words in CSV not in word bank and will be skipped: '
                           f'{", ".join(sorted(unknown_words)[:8])}{"…" if len(unknown_words)>8 else ""}')

        def parse_row_mastered(row):
            mastered = set()
            for col_idx, word in word_cols:
                if word in bank_words and col_idx < len(row) and row[col_idx].strip() == '1':
                    mastered.add(word)
            return mastered

        def get_fields(row):
            return (row[fi].strip().title() if fi < len(row) else '',
                    row[li].strip().title() if li < len(row) else '',
                    row[ci].strip().upper() if ci < len(row) else '')

    def compute_word_pos(mastered):
        pos = YEAR_WORD_ZONE.get(yr, 0)
        for i, (word, *_) in enumerate(WORD_BANK):
            if word in mastered:
                pos = i + 1
        return pos

    # Group by class
    by_class = {}
    for i, row in enumerate(rows):
        if not any(v.strip() for v in row):
            continue  # skip blank rows
        first, last, suffix = get_fields(row)
        if not first:
            continue
        class_id = cls_map.get(suffix)
        if not class_id:
            warnings.append(f'Row {i+2}: unknown class "{suffix}" for Y{yr} — skipped')
            continue
        by_class.setdefault(class_id, []).append((first, last, parse_row_mastered(row)))

    created = updated = skipped = 0

    for class_id, class_rows in by_class.items():
        path = f'data/classes/{class_id}.json'
        data, sha = _get_file(path)
        if not data:
            warnings.append(f'Could not load {class_id}')
            continue

        name_map = {}
        for idx, p in enumerate(data.get('pupils', [])):
            key = (p.get('first','').strip().lower(), p.get('last','').strip().lower())
            name_map[key] = idx

        suffix_short = class_id.split('_')[1]

        for first, last, incoming in class_rows:
            incoming = incoming & bank_words  # ensure only valid words
            key = (first.lower(), last.lower())

            if key in name_map:
                idx      = name_map[key]
                existing = set(data['pupils'][idx].get('mastered', []))
                merged   = sorted(existing | incoming) if on_conflict == 'merge' else sorted(incoming)
                data['pupils'][idx]['mastered']  = merged
                data['pupils'][idx]['word_pos']  = compute_word_pos(set(merged))
                updated += 1
            else:
                existing_ids = {p['id'] for p in data['pupils']}
                max_n = max((int(pid[1:]) for pid in existing_ids
                             if pid.startswith('p') and pid[1:].isdigit()), default=0)
                pid      = f'p{max_n+1:02d}'
                mastered = sorted(incoming)
                data['pupils'].append({
                    'id': pid, 'first': first, 'last': last,
                    'cls': suffix_short, 'group': 'main',
                    'tt_set': '2', 'tt_mode': 'x', 'table': '',
                    'adapted_hl': False, 'pair_id': '', 'pair_colour': '',
                    'word_pos': compute_word_pos(set(mastered)),
                    'mastered': mastered, 'rule_confidence': {},
                    'homophone_mastered': [], 'homophone_history': {},
                    'ss_user': '', 'ss_pass': '',
                })
                name_map[key] = len(data['pupils']) - 1
                created += 1

        ok = _put_file(path, data, sha,
                       f'Mastery import Y{yr}: {class_id} ({created} new, {updated} updated)')
        if not ok:
            return {'ok': False, 'error': f'GitHub write failed for {class_id}'}

    return {'ok': True, 'created': created, 'updated': updated,
            'skipped': skipped, 'warnings': warnings}

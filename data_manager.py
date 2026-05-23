"""
data_manager.py — WFA Flask app data layer
Data lives in wallscourtfarm/spelling-homelearning GitHub repo.
"""
import os, json, base64, requests
from word_bank import WORD_BANK, get_active_words, mastery_stats

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
DATA_REPO    = os.environ.get('DATA_REPO', 'wallscourtfarm/spelling-homelearning')
BRANCH       = 'main'
HEADERS      = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
BASE_URL     = f'https://api.github.com/repos/{DATA_REPO}/contents'

TT_ORDER   = ['2','5','4','8','3','6','9','7','11','12','All']
ALL_CLASSES = ['Y4_IM','Y4_WU']

# ── GitHub I/O ────────────────────────────────────────────────────────────────

def _get_file(path):
    r = requests.get(f'{BASE_URL}/{path}', headers=HEADERS, timeout=10)
    if r.status_code == 200:
        d = r.json()
        return json.loads(base64.b64decode(d['content']).decode('utf-8')), d['sha']
    return None, None

def _put_file(path, data, sha, message):
    content = base64.b64encode(
        json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
    ).decode('utf-8')
    r = requests.put(f'{BASE_URL}/{path}', headers=HEADERS,
                     json={'message':message,'content':content,'sha':sha,'branch':BRANCH}, timeout=15)
    return r.status_code in (200, 201)

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
    if not rule_id_str: return None
    try:
        from spelling_rules import SPELLING_RULES
        stage, step = int(rule_id_str.split('-')[0]), int(rule_id_str.split('-')[1])
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
        'first':     p.get('first',''),
        'last':      p.get('last',''),
        'group':     p.get('group','main'),
        'cls':       p.get('cls',''),
        'tt':        tt_label(ts, tm),
        'tt_set':    ts,
        'y4_pct':    s.get('Y4',0),
        'phase_pct': s.get('LKS2',0),
        'ks_pct':    s.get('KS2',0),
        'all_pct':   s.get('total',0),
    }

def load_dashboard(class_id='Y4_IM'):
    if class_id == 'all':
        all_pupils = []
        for cid in ALL_CLASSES:
            d = load_class(cid)
            if d: all_pupils.extend(d.get('pupils',[]))
    else:
        d = load_class(class_id)
        if not d: return None
        all_pupils = d.get('pupils',[])

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
        pupils.append({'id':p['id'],'first':p.get('first',''),'cls':p.get('cls',''),
                       'group':p.get('group','main'),'is_rev':is_rev,
                       'rule_label': rule[2] if rule else ('Revision' if is_rev else 'Main'),
                       'words': words})
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
            data['pupils'][i] = _apply_assessment(p, words); saved+=1
    if saved and not _put_file(path,data,sha,f'Spelling Bee: {class_id} ({saved} pupils)'):
        return {'ok':False,'error':'GitHub write failed'}
    return {'ok':True,'saved':saved}

# ── Learners ──────────────────────────────────────────────────────────────────

def load_learners(class_id='Y4_IM'):
    # Build cross-class id->name map for partner resolution
    all_data = {}
    for cid in ALL_CLASSES:
        d = load_class(cid)
        if d:
            for p in d.get('pupils', []):
                all_data[p['id']] = p.get('first') or '?'

    if class_id == 'all':
        pupils = []
        for cid in ALL_CLASSES:
            d = load_class(cid)
            if d:
                pupils.extend(d.get('pupils', []))
    else:
        d = load_class(class_id)
        if not d:
            return []
        pupils = d.get('pupils', [])

    result = []
    for p in pupils:
        pid = p.get('pair_id', '')
        partner = all_data.get(pid, '—') if pid else '—'
        result.append({**p, 'partner_name': partner})
    return result

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
                for r in SPELLING_RULES if r[4] != 1]
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

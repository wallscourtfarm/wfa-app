"""
data_manager.py — WFA Flask app data layer
Data lives in wallscourtfarm/spelling-homelearning GitHub repo.
"""
import os, json, base64, requests, time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from word_bank import WORD_BANK, get_active_words, mastery_stats, next_active_index

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
DATA_REPO    = os.environ.get('DATA_REPO', 'wallscourtfarm/spelling-homelearning')
BRANCH       = 'main'
HEADERS      = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
BASE_URL     = f'https://api.github.com/repos/{DATA_REPO}/contents'

TT_ORDER   = ['2','5','4','8','3','6','9','7','11','12','All']

# ── Class registry ─────────────────────────────────────────────────────────────
# Single source of truth for 2026-27. Class IDs use the format YN_XX.

YEAR_GROUP_CLASSES = {
    '1': ['1ER', '1JS'],
    '2': ['2MY', '2JH'],
    '3': ['3JW', '3WU'],
    '4': ['4CC', '4RB'],
    '5': ['5LS', '5IM'],
    '6': ['6JM', '6SD'],
}

ALL_CLASSES = [c for classes in YEAR_GROUP_CLASSES.values() for c in classes]

YEAR_WORD_ZONE = {
    '1': 21, '2': 78, '3': 131, '4': 185, '5': 239, '6': 290,
}

def get_year_group(class_id):
    """Return year group string ('1'–'6') for a class_id, or None."""
    import re as _re
    for yr, classes in YEAR_GROUP_CLASSES.items():
        if class_id in classes:
            return yr
    # Handle Y4_all or Y4_IM style
    m = _re.match(r'Y(\d+)', class_id or '')
    if m:
        return m.group(1)
    return None

def _resolve_classes(class_id):
    """
    Return list of real class IDs to load.
      'Y4_all' -> ['Y4_IM', 'Y4_WU']
      'Y4_IM'  -> ['Y4_IM']
      'all'    -> ['Y4_IM', 'Y4_WU']  (Y4 fallback)
    """
    if class_id == 'all':
        return list(YEAR_GROUP_CLASSES.get('4', []))
    if class_id and class_id.endswith('_all'):
        import re as _re
        m = _re.match(r'Y(\d+)', class_id)
        yr = m.group(1) if m else class_id[1]
        return list(YEAR_GROUP_CLASSES.get(yr, []))
    return [class_id] if class_id else []

def get_ref_class(class_id):
    """Single real class ID for config lookups when an _all selector is used."""
    classes = _resolve_classes(class_id)
    return classes[0] if classes else '4CK'

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
            suffix = cid.lstrip('0123456789')
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

def _is_legacy_weekly_config(data):
    """Old shape: a single flat config dict, not yet keyed by year group."""
    return isinstance(data, dict) and ('year_group' in data or 'lesson_ids' in data)

def _migrate_legacy_weekly_config(data):
    """Wrap a pre-migration flat weekly_config under whichever year it was
    actually configured for, so existing data isn't lost on first read."""
    legacy_yr = str(data.get('year_group', '')).lstrip('Yy') or '4'
    return {legacy_yr: data}

def load_weekly_config(year_group):
    """Each year group has its own weekly ULS config — a Y2 week has nothing
    to do with a Y5 week. `year_group` is the bare digit string ('1'-'6')."""
    data, _ = _get_file('data/weekly_config.json')
    if not data:
        return {}
    if _is_legacy_weekly_config(data):
        data = _migrate_legacy_weekly_config(data)
    return data.get(str(year_group), {})

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

def get_uls_lesson(lesson_id):
    """Return a ULS lesson dict by ID like 'y4-t1-w2-l1', or None."""
    from uls_lessons import get_lesson
    return get_lesson(lesson_id)

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
        'revision':     sum(1 for p in all_pupils if p.get('group') in ('revision','phonics')),
        'paired':       sum(1 for p in all_pupils if p.get('pair_id')),
        'avg_mastered': sum(len(p.get('mastered',[])) for p in all_pupils) // max(len(all_pupils),1),
    }
    return {'rows': rows, 'tt_dist': tt_dist, 'stats': stats}

# ── Lowest Confidence Key Spellings ───────────────────────────────────────────────

def lowest_confidence_key_spellings(class_id='Y4_all', year=None, top_n=10):
    """Return top_n words most commonly unmastered across pupils.
    Y3+: Key Spellings from current year and all prior years.
    Y2:  CEW/HFW words from R and Y1 (the zone they've just been assessed on).
    Y1:  returns [] — new starters have no prior assessment data.
    """
    class_ids = _resolve_classes(class_id)
    class_data = _load_classes_parallel(class_ids)
    all_pupils = []
    for cid in class_ids:
        d = class_data.get(cid)
        if d: all_pupils.extend(d.get('pupils', []))
    if not all_pupils:
        return []

    if year == '1':
        return []  # new starters — no prior data to surface

    if year == '2':
        # Show most commonly unmastered R and Y1 CEW/HFW words
        candidate_words = [w for w, yr, ks, phase, label in WORD_BANK
                           if yr in ('R', '1') and label in ('CEW', 'HFW')]
    else:
        # Y3+: Key Spellings from current year and all prior years
        YEAR_ORDER = ['3', '4', '5', '6']
        if year and year in YEAR_ORDER:
            include_years = set(YEAR_ORDER[:YEAR_ORDER.index(year) + 1])
        else:
            include_years = None  # no filter — include all
        candidate_words = [w for w, yr, ks, phase, label in WORD_BANK
                           if label == 'Key Spelling' and (include_years is None or yr in include_years)]

    if not candidate_words:
        return []
    total = len(all_pupils)
    # Build list preserving WORD_BANK order (index = tiebreaker: lower index = earlier/lower year)
    word_index = {w.lower(): i for i, w in enumerate(candidate_words)}
    counts = {}
    for word in candidate_words:
        wl = word.lower()
        counts[wl] = sum(1 for p in all_pupils if wl not in {m.lower() for m in p.get('mastered', [])})
    # Primary: most unmastered first; tiebreaker: lower year group word (earlier in WORD_BANK) first
    sorted_words = sorted(counts.items(), key=lambda x: (-x[1], word_index[x[0]]))[:top_n]
    return [{'word': w, 'unmastered': c, 'total': total,
             'pct': round(c / total * 100) if total else 0}
            for w, c in sorted_words]

# ── TT Check ─────────────────────────────────────────────────────────────────

def load_tt_pupils(class_id='4CK'):
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

def _group_words_by_lesson(words, lessons):
    """
    Group a flat word list (e.g. weekly_config's selected_words) by which
    lesson/rule each word actually belongs to, so a week that mixes several
    rules in one 5-word pick (e.g. -ing/-ed/-ly all taught the same week)
    still reports confidence separately per rule, even though there's only
    one word-picker. A rule with none of its words selected doesn't appear;
    a week with only one lesson naturally collapses to a single group.
    Returns [{'lesson_id', 'title', 'words'}], in first-seen order.
    """
    word_to_lesson = {}
    for l in lessons:
        for w in l.get('hlWords', []):
            word_to_lesson.setdefault(w, l)
    groups, index = [], {}
    for w in words:
        l = word_to_lesson.get(w)
        lesson_id = l['id'] if l else ''
        title = l['focus'] if l else ''
        if lesson_id not in index:
            index[lesson_id] = {'lesson_id': lesson_id, 'title': title, 'words': []}
            groups.append(index[lesson_id])
        index[lesson_id]['words'].append(w)
    return groups


def load_bee_pupils(class_id='4CK'):
    data = load_class(class_id)
    wc   = load_weekly_config(get_year_group(class_id) or '4')
    if not data: return [], {}, ''
    # ULS: get this week's lesson focuses
    from uls_lessons import get_lesson, TERM_LABELS
    lesson_ids = wc.get('lesson_ids', [])
    lessons    = [get_lesson(lid) for lid in lesson_ids if get_lesson(lid)]
    week_focuses = [l['focus'] for l in lessons] if lessons else []
    hl_words   = wc.get('selected_words', [])
    # The Bee's rule words are this week's HL words (selected_words) — the
    # same 5 words already picked for Home Learning — grouped by whichever
    # rule each word actually belongs to, so mixed-rule weeks still get
    # separate confidence per rule.
    rule_groups = _group_words_by_lesson(hl_words, lessons)

    # Build week label e.g. "T1 W2 · Spring 1"
    term_label = TERM_LABELS.get(wc.get('term',''), wc.get('term',''))
    week_label = f"{wc.get('term','')} W{wc.get('week','')} · {term_label}" if wc.get('term') else wc.get('week_ref','')

    from phonics_bank import PHONICS_BANK, get_phonics_words
    pupils = []
    for p in data.get('pupils',[]):
        mastered   = set(p.get('mastered',[]))
        key_words  = get_active_words(p.get('word_pos',0), mastered, 5)
        group      = p.get('group','main')
        is_phonics = group in ('phonics', 'revision')
        gpcs       = p.get('phonics_gpcs', [])
        if is_phonics and gpcs:
            phonics_words = get_phonics_words(gpcs, PHONICS_BANK)
            gpc_label = ', '.join(gpcs)
        else:
            phonics_words = []
            gpc_label = ''
        pupils.append({'id':p['id'],'first':p.get('first',''),'cls':p.get('cls',''),'file_cls':class_id,
                       'group': group, 'is_phonics': is_phonics,
                       'phonics_gpcs': gpcs, 'gpc_label': gpc_label,
                       'phonics_words': phonics_words,
                       'rule_label': wc.get('year_group','') + ' ' + week_label,
                       'words': key_words,
                       'words_updated_at': p.get('words_updated_at','')})
    # Build rules_info for template display
    focuses_str = ' · '.join(week_focuses[:2]) if week_focuses else '—'
    rules_info = {
        'main':      focuses_str,
        'phonics':   'Phonics GPC words',
        'week':      wc.get('week_ref', week_label),
        'hl_words':  hl_words,
        'lessons':   lessons,
        'rule_groups': rule_groups,
        'year_group': wc.get('year_group', ''),
    }
    return pupils, rules_info, wc.get('week_ref', week_label)


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

def save_weekly_config(year_group, data):
    """Save one year group's weekly ULS config back to GitHub, without
    touching any other year group's config in the same file. Self-migrates
    a pre-migration flat file to the per-year-group shape on first save."""
    all_data, sha = _get_file('data/weekly_config.json')
    if all_data is None:
        all_data, sha = {}, None
    elif _is_legacy_weekly_config(all_data):
        all_data = _migrate_legacy_weekly_config(all_data)
    all_data[str(year_group)] = data
    if sha is None:
        return _put_file_create('data/weekly_config.json', all_data, f'Update weekly config (Y{year_group})')
    return _put_file('data/weekly_config.json', all_data, sha, f'Update weekly config (Y{year_group})')


def list_plannable_rules():
    """All plannable rules (standard + custom) for Settings dropdowns."""
    from spelling_rules import SPELLING_RULES
    custom_rules = load_custom_rules()
    custom   = [(f'0-{cr["id"]}', f'Custom: {cr["title"]}') for cr in custom_rules]
    standard = [(f'{r[0]}-{r[1]}', f'S{r[0]} Step {r[1]}: {r[2]}')
                for r in SPELLING_RULES if r[4] == 0]
    return custom + standard

def list_uls_weeks(year_group):
    """Return list of (week_code, label) tuples for a given year group, e.g. 'T1W1'."""
    from uls_lessons import get_all_weeks, TERM_LABELS
    result = []
    for term, week in get_all_weeks(year_group):
        code  = f'{term}W{week}'
        label = f'{term} W{week} — {TERM_LABELS.get(term, term)}'
        result.append((code, label))
    return result

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

def _bee_rules_by_class(assessments):
    """Group a Bee save's assessments by class, and for each class resolve
    that year group's rule words this week — the same 5 words already
    selected for Home Learning (weekly_config's selected_words), grouped by
    whichever rule/lesson each word actually belongs to (a week can mix
    several rules in one 5-word pick, e.g. -ing/-ed/-ly together):
    {lesson_id: {'title': focus, 'total': n_words_for_that_rule}}.
    Shared helper for both functions below."""
    from uls_lessons import get_lesson

    by_class = {}
    for a in assessments:
        by_class.setdefault(a.get('cls', ''), []).append(a)

    result = {}
    for cls_id, ass_list in by_class.items():
        if not cls_id:
            continue
        wc = load_weekly_config(get_year_group(cls_id) or '4')
        words = wc.get('selected_words', [])
        lesson_ids = wc.get('lesson_ids', [])
        lessons = [get_lesson(lid) for lid in lesson_ids if get_lesson(lid)]
        groups = _group_words_by_lesson(words, lessons)
        rules = {g['lesson_id']: {'title': g['title'], 'total': len(g['words'])}
                for g in groups if g['lesson_id']}
        result[cls_id] = {'assessments': ass_list, 'week_ref': wc.get('week_ref', ''), 'rules': rules}
    return result


def update_rule_confidence_from_bee(assessments):
    """
    Given a list of {pupil_id, cls, rules: [{lesson_id, correct_words}]}
    dicts from a Bee save, tally word-level correctness per rule (across all
    classes/pupils in this save) and update rule_confidence.json — the
    whole-school dot indicators shown on the Rules page.

    Proportion thresholds: <40% → Low (1), 40–70% → Medium (2), >70% → High (3).
    Only rules that had at least one pupil assessed are updated — rules with
    no data this session are left unchanged so manual settings are preserved.
    """
    if not assessments:
        return False

    by_class = _bee_rules_by_class(assessments)

    # Tally per lesson: {lesson_id: [total_words_possible, total_correct]}
    tally = {}
    for cls_id, info in by_class.items():
        rules = info['rules']
        for a in info['assessments']:
            for r in a.get('rules', []):
                lesson_id = r.get('lesson_id', '')
                cfg = rules.get(lesson_id)
                if not cfg:
                    continue
                correct = len(r.get('correct_words', []))
                if lesson_id not in tally:
                    tally[lesson_id] = [0, 0]
                tally[lesson_id][0] += cfg['total']
                tally[lesson_id][1] += correct

    if not tally:
        return False

    def _level(total, correct):
        if total == 0:
            return 0
        pct = correct / total
        if pct > 0.70:
            return 3  # High
        if pct >= 0.40:
            return 2  # Medium
        return 1      # Low

    conf = load_rule_confidence()
    for rule_id, (total, correct) in tally.items():
        conf[rule_id] = {'level': _level(total, correct)}

    return save_rule_confidence(conf)


def update_pupil_rule_confidence_from_bee(assessments):
    """
    Companion to update_rule_confidence_from_bee: appends a rule_confidence
    entry to each individually-assessed pupil's own record (the same field
    the Rule Reassessment tool writes to), so the dashboard's per-pupil Rule
    Confidence panel builds up week by week straight from the Bee.

    A week can cover several distinct rules — every rule a pupil has words
    marked for gets its own entry, with status derived from correct/total
    words marked (matching Rule Reassessment's thresholds), not a manual
    tick. Does not touch mastered/word_pos.
    """
    if not assessments:
        return {'ok': True, 'updated': 0}

    by_class = _bee_rules_by_class(assessments)
    today = datetime.now(timezone.utc).date().isoformat()

    total_updated = 0
    for cls_id, info in by_class.items():
        rules = info['rules']
        if not rules:
            continue
        path = f'data/classes/{cls_id}.json'
        data, sha = _get_file(path)
        if not data:
            continue
        ass_map = {a['pupil_id']: a for a in info['assessments']}
        changed = False
        class_updated = 0
        for i, p in enumerate(data.get('pupils', [])):
            entry_in = ass_map.get(p['id'])
            if entry_in is None:
                continue
            rc = dict(p.get('rule_confidence') or {})
            row_changed = False
            for r in entry_in.get('rules', []):
                lesson_id = r.get('lesson_id', '')
                cfg = rules.get(lesson_id)
                if not cfg:
                    continue
                correct = len(r.get('correct_words', []))
                total   = cfg['total']
                score   = round(correct / total * 100) if total else 0
                if correct == total:
                    status = 'full'
                elif correct > 0:
                    status = 'partial'
                else:
                    status = 'none'
                history = list(rc.get(lesson_id, []))
                history.append({
                    'week':    info['week_ref'],
                    'date':    today,
                    'correct': correct,
                    'total':   total,
                    'score':   score,
                    'status':  status,
                    'rule':    cfg['title'],
                    'source':  'bee',
                })
                rc[lesson_id] = history
                row_changed = True
            if row_changed:
                p = dict(p)
                p['rule_confidence'] = rc
                data['pupils'][i] = p
                changed = True
                class_updated += 1
                total_updated += 1
        if changed:
            _put_file(path, data, sha, f'Bee rule confidence: {cls_id} ({class_updated} pupils)')

    return {'ok': True, 'updated': total_updated}


def latest_rule_confidence_entry(entries):
    """
    Pick the entry that represents a rule's *current* confidence out of its
    history list. A full Rule Reassessment ('source': 'reassessment') is a
    proper word-by-word test and is authoritative: once one exists for a
    rule, it always wins over any weekly Bee tick ('source': 'bee'), even if
    a Bee save happens to land later in the list. Among reassessment entries
    (or among plain entries with no 'source' tag — e.g. pre-migration data),
    the most recent one wins as before.
    """
    if not entries:
        return None
    reassessments = [e for e in entries if e.get('source') == 'reassessment']
    return reassessments[-1] if reassessments else entries[-1]


# ── Per-pupil rule confidence archive/reset (ULS migration) ────────────────────
# The per-pupil `rule_confidence` field (dashboard "Rule confidence" panel) holds
# assessment history keyed by the old Spelling Shed rule IDs (e.g. "4-1"). After
# switching to Unlocking Letters & Sounds those IDs no longer mean anything, so
# this archives the data (never deletes it) and clears the live field. It does
# NOT touch mastered/word_pos/homophone_mastered — those track the CEW/Key
# Spelling list, which is unaffected by the ULS change.

def get_rule_confidence_summary():
    """Dry-run: how much rule_confidence data exists right now, per class."""
    summary = {'classes': {}, 'total_pupils': 0, 'total_entries': 0}
    for cid in ALL_CLASSES:
        data = load_class(cid)
        if not data:
            continue
        n_pupils, n_entries = 0, 0
        for p in data.get('pupils', []):
            rc = p.get('rule_confidence') or {}
            if rc:
                n_pupils += 1
                n_entries += sum(len(v) for v in rc.values())
        if n_pupils:
            summary['classes'][cid] = {'pupils': n_pupils, 'entries': n_entries}
        summary['total_pupils']  += n_pupils
        summary['total_entries'] += n_entries
    return summary


def archive_and_reset_rule_confidence():
    """
    Archive every pupil's current rule_confidence to a dated backup file under
    data/archive/, then clear rule_confidence to {} for every pupil who had
    data. Pupils with no rule_confidence are left untouched (no-op write).
    Returns {'ok': True, 'archived': n, 'reset': n, 'archive_path': ...}.
    """
    import datetime
    stamp = datetime.date.today().isoformat()
    archive = {
        'archived_date': stamp,
        'reason': 'ULS migration — Spelling Shed rule confidence retired',
        'classes': {},
    }
    total_pupils = 0
    class_snapshots = []

    for cid in ALL_CLASSES:
        path = f'data/classes/{cid}.json'
        data, sha = _get_file(path)
        if not data:
            continue
        class_snapshots.append((cid, path, data, sha))
        archived_pupils = []
        for p in data.get('pupils', []):
            rc = p.get('rule_confidence') or {}
            if rc:
                archived_pupils.append({
                    'id': p.get('id', ''), 'first': p.get('first', ''),
                    'last': p.get('last', ''), 'rule_confidence': rc,
                })
        if archived_pupils:
            archive['classes'][cid] = archived_pupils
            total_pupils += len(archived_pupils)

    archive['total_pupils'] = total_pupils
    if total_pupils == 0:
        return {'ok': True, 'archived': 0, 'reset': 0,
                'note': 'No rule confidence data found — nothing to do.'}

    archive_path = f'data/archive/rule_confidence_backup_{stamp}.json'
    if not _put_file_create(archive_path, archive,
                            f'Archive rule confidence before ULS reset ({total_pupils} pupils, {stamp})'):
        return {'ok': False, 'error': f'Failed to write archive file {archive_path} — nothing was reset'}

    reset_count = 0
    for cid, path, data, sha in class_snapshots:
        changed = False
        for p in data.get('pupils', []):
            if p.get('rule_confidence'):
                p['rule_confidence'] = {}
                reset_count += 1
                changed = True
        if changed:
            if not _put_file(path, data, sha, f'Reset rule confidence (ULS migration): {cid}'):
                return {'ok': False,
                        'error': f'Archived OK, but failed to reset {path} — some pupils may still show old data',
                        'archived': total_pupils, 'reset': reset_count, 'archive_path': archive_path}

    return {'ok': True, 'archived': total_pupils, 'reset': reset_count, 'archive_path': archive_path}


def load_term_dates():
    """Load term weeks from data/term_dates.json.
    Returns list of {label, iso, display, term, week} dicts, or [] on failure."""
    content, _ = _get_file("data/term_dates.json")
    return content or []


def current_week_ref(term_dates=None):
    """Return the TxWy label for today's date, or None if outside term time.
    Each term_dates entry has {label, iso, term, week}. Weeks run Mon–Sun."""
    import datetime
    if term_dates is None:
        term_dates = load_term_dates()
    if not term_dates:
        return None
    today = datetime.date.today().isoformat()
    # Sort by iso date ascending
    dated = sorted([w for w in term_dates if w.get('iso')], key=lambda w: w['iso'])
    current = None
    for w in dated:
        if w['iso'] <= today:
            current = w
        else:
            break
    if not current:
        return None
    # Check we're within 7 days of that week's start (Mon–Sun)
    import datetime as dt
    start = dt.date.fromisoformat(current['iso'])
    end   = start + dt.timedelta(days=6)
    if dt.date.today() <= end:
        return current.get('label')
    return None  # date is after the last known week

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
        suffix = cid.lstrip('0123456789')
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
    cls_map = {cid.lstrip('0123456789').upper(): cid for cid in classes}
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
        # First not-yet-mastered word from the very start of the whole
        # list — a pupil's real position, independent of year group.
        return next_active_index(0, mastered)

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

        suffix_short = class_id.lstrip('0123456789')

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
                # No matching pupil already on roll — never create one here.
                # Pupils only ever enter via Roster Import (Bromcom); a
                # mastery row for someone not yet on roll is reported, not
                # used to mint a new identity.
                warnings.append(f'{first} {last} ({suffix_short}): no matching pupil on roll — skipped')
                skipped += 1

        ok = _put_file(path, data, sha,
                       f'Mastery import Y{yr}: {class_id} ({created} new, {updated} updated)')
        if not ok:
            return {'ok': False, 'error': f'GitHub write failed for {class_id}'}

    return {'ok': True, 'created': created, 'updated': updated,
            'skipped': skipped, 'warnings': warnings}

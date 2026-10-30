"""Run with plain python:  python3 tests/test_pupil_ids.py
Proves, against an in-memory fake of the GitHub helpers, the roster-sync
pupil_id handling and
that staff JSON carries `pid` but never first/last/name/upn. Fake names only."""
import os, sys, json, copy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('GITHUB_TOKEN', 'x')
os.environ.setdefault('ACCESS_GATE', 'off')   # test client has no Cloudflare sign-in

import roster_sync

NAME_BITS = ['Zebulon', 'Quillfeather', 'Zara', 'Quimby', 'Wilbur', 'Fenwick', 'Dribble',
             'Ottoline', 'Pennywhistle', 'A1234567890']


def assert_clean(text, where):
    for bit in NAME_BITS:
        assert bit not in text, f'{where}: leaked {bit!r}'


def pupil(pid, first, last, upn, **extra):
    d = {'id': pid, 'first': first, 'last': last, 'cls': 'IM', 'upn': upn, 'group': 'main',
         'tt_set': '2', 'tt_mode': 'x', 'pair_id': '', 'pair_colour': '', 'table': '1',
         'word_pos': 0, 'mastered': ['about'], 'us_pin': '1234'}
    d.update(extra)
    return d


def make_store():
    return {
        'data/classes/5IM.json': {'class_id': '5IM', 'pupils': [
            pupil('p01', 'Zebulon', 'Quillfeather', 'A123456789012'),
            pupil('p02', 'Zara', 'Quimby', 'A123456789013', pupil_id='p_oldcode001'),
            pupil('p03', 'Wilbur', 'Fenwick-Dribble', ''),                 # no UPN
            pupil('p04', 'Ottoline', 'Pennywhistle', 'A123456789099'),     # not on roster
        ]},
        'data/classes/5LS.json': {'class_id': '5LS', 'pupils': [
            pupil('p05', 'Zebulon', 'Quimby', 'A123456789015'),            # roster has no code
            pupil('p06', 'Wilbur', 'Quillfeather', 'A123456789016', pupil_id='p_samecode06'),  # already right
        ]},
    }


ROSTER = [
    {'upn': 'A123456789012', 'pupilId': 'p_k3m9x2q7ab', 'first': 'Zebulon', 'last': 'Quillfeather'},
    {'upn': 'A123456789013', 'pupilId': 'p_newcode002', 'first': 'Zara', 'last': 'Quimby'},
    {'upn': 'A123456789015', 'first': 'Zebulon', 'last': 'Quimby'},
    {'upn': 'A123456789016', 'pupilId': 'p_samecode06', 'first': 'Wilbur', 'last': 'Quillfeather'},
    # a roster entry that would match p03 BY NAME must never be used
    {'upn': 'A123456789777', 'pupilId': 'p_byname0000', 'first': 'Wilbur', 'last': 'Fenwick-Dribble'},
]


class FakeGitHub:
    def __init__(self, store):
        self.store = store
        self.shas = {k: 1 for k in store}
        self.puts = []          # (path, message)
        self.fail_next_put = 0  # simulate stale-sha conflicts
        self.on_conflict = None  # callable run when a conflict is simulated (concurrent edit)

    def get(self, path):
        if path not in self.store:
            return None, None
        return copy.deepcopy(self.store[path]), f'sha{self.shas[path]}'

    def put(self, path, obj, sha, message):
        if self.fail_next_put:
            self.fail_next_put -= 1
            if self.on_conflict:
                self.on_conflict(self)
            return False
        if path not in self.store:          # new file (e.g. roster meta)
            self.shas[path] = 0
        elif sha != f'sha{self.shas[path]}':
            return False
        self.store[path] = copy.deepcopy(obj)
        self.shas[path] += 1
        self.puts.append((path, message))
        return True


def install(store):
    fake = FakeGitHub(store)
    roster_sync._gh_get = fake.get
    roster_sync._gh_put = fake.put
    return fake


# ── normal sync sets pupil_id on matched pupils and new pupils ──────────────
store = make_store()
fake = install(store)
roster_sync.fetch_classes = lambda: []
full_roster = ROSTER[:4] + [
    {'upn': 'A123456789888', 'pupilId': 'p_newpupil88', 'first': 'Ottoline', 'last': 'Newcomer', 'class': '5IM'},
]
for r in full_roster[:4]:
    r['class'] = '5IM' if r['upn'] in ('A123456789012', 'A123456789013') else '5LS'
roster_sync.MIN_ROSTER_RATIO = 0.0
res = roster_sync.sync_roster(apply=True, remove_leavers=False, roster=full_roster)
assert res['ok'], res
im = {p['id']: p for p in store['data/classes/5IM.json']['pupils']}
assert im['p01']['pupil_id'] == 'p_k3m9x2q7ab' and im['p02']['pupil_id'] == 'p_newcode002'
newp = [p for p in store['data/classes/5IM.json']['pupils'] if p.get('pupil_id') == 'p_newpupil88']
assert len(newp) == 1 and newp[0]['upn'] == ''      # class files no longer carry a UPN (18.10.26)
print('roster sync pupil_id OK')

# ── staff JSON: pid present, no first/last/name/upn anywhere ────────────────
import data_manager
import app as appmod
flask_app = appmod.app
flask_app.config['TESTING'] = True


def walk_keys(o, path=''):
    if isinstance(o, dict):
        for k, v in o.items():
            assert k not in ('first', 'last', 'name', 'upn'), f'forbidden key {path}/{k}'
            walk_keys(v, f'{path}/{k}')
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk_keys(v, f'{path}[{i}]')


def collect(o, key, acc):
    if isinstance(o, dict):
        if key in o:
            acc.append(o[key])
        for v in o.values():
            collect(v, key, acc)
    elif isinstance(o, list):
        for v in o:
            collect(v, key, acc)
    return acc


CODES = {'p01': 'p_k3m9x2q7ab', 'p02': 'p_newcode002', 'p03': 'p_wilbur0003'}
FAKE = [pupil('p01', 'Zebulon', 'Quillfeather', 'A123456789012', pupil_id=CODES['p01']),
        pupil('p02', 'Zara', 'Quimby', 'A123456789013', pupil_id=CODES['p02']),
        pupil('p03', 'Wilbur', 'Fenwick-Dribble', 'A123456789014', pupil_id=CODES['p03'])]
FAKE[0]['pair_id'] = 'p02'; FAKE[1]['pair_id'] = 'p01'

import routes.tt as rtt, routes.class_manager as rcm, routes.dashboard as rdash, routes.bee as rbee

# tt: real load_tt_pupils over a fake class file
data_manager.load_class = lambda cid: {'pupils': copy.deepcopy(FAKE)}
rtt.load_tt_pupils = data_manager.load_tt_pupils
data_manager._resolve_classes = lambda c: ['5IM']
rtt.get_class_options_for_year = lambda yr: [('Y5_all', 'All')]

# dashboard
rows = [data_manager._pupil_row(p) for p in FAKE]
assert [r['pid'] for r in rows] == list(CODES.values())
rdash.load_dashboard = lambda cls: {'rows': rows, 'tt_dist': {}, 'stats': {'total': 3, 'main': 3, 'revision': 0, 'paired': 2, 'avg_mastered': 0}}
rdash.lowest_confidence_key_spellings = lambda *a, **k: []
rdash.load_learners = lambda cls: copy.deepcopy(FAKE)
rdash.get_class_options_for_year = lambda yr: [('Y5_all', 'All')]

# bee: real load_bee_pupils row shape
def fake_bee(cid, week):
    ps = [{'id': p['id'], 'pid': p.get('pupil_id', ''), 'first': p['first'], 'last': p['last'], 'cls': 'IM',
           'file_cls': cid, 'group': 'main', 'is_phonics': False, 'gpc_label': '', 'phonics_words': [],
           'rule_label': '', 'words': ['about'], 'marked_key': [], 'marked_rule': [],
           'words_updated_at': ''} for p in FAKE]
    return ps, {'main': '-', 'lessons': [], 'rule_groups': {}, 'hl_words': [], 'week': 'T1W1', 'year_group': 'Y5'}, 'T1W1'
rbee.load_bee_pupils = fake_bee
rbee.get_bee_weeks = lambda yr: ([], 'T1W1')
rbee.week_needing_marking = lambda cls, cur: 'T1W1'
rbee._resolve_classes = lambda cls: ['5IM']
rbee.get_class_options_for_year = lambda yr: [('Y5_all', 'All')]

import re
with flask_app.test_client() as c:
    with c.session_transaction() as s:
        s['year_group'] = '5'
        s['authed'] = True

    d = c.get('/api/tt/data').get_json()
    walk_keys(d)
    assert sorted(collect(d, 'pid', [])) == sorted(CODES.values()), d
    assert_clean(json.dumps(d), '/api/tt/data')

    for url in ('/dashboard', '/spelling-bee', '/tt'):
        r = c.get(url)
        body = r.get_data(as_text=True)
        assert r.status_code == 200, (url, r.status_code, body[:300])
        assert_clean(body, url)
        tagged = re.findall(r'<span data-pupil-id="([^"]*)">([^<]*)</span>', body)
        assert sorted(t[0] for t in tagged if t[0]) == sorted(CODES.values()), (url, tagged)
        assert all(t[1].strip() and len(t[1]) <= 8 for t in tagged), (url, tagged)   # label only
        # base.html loads the shared helper on staff pages
        assert 'wfa-shared@main/web/names-file.js' in body and 'WFANames.screen.init()' in body, url
        print(url, 'OK: tagged', len(tagged), 'labels')

    # class manager list
    rcm._load_class_file = lambda cid: ({'pupils': copy.deepcopy(FAKE)}, 'sha')
    rcm.ALL_CLASSES = ['5IM']
    rcm.reading_ladder_for_year = lambda y: ['5', '4', 'phonics']
    d = c.get('/api/class/list?cls=5IM').get_json()
    assert d['ok'], d
    walk_keys(d)
    assert_clean(json.dumps(d), '/api/class/list')
    assert [p['pid'] for p in d['pupils']] and all(p['pid'] for p in d['pupils'])
    assert all(p['pid'] for p in d['all_pupils'])
    by_id = {p['id']: p for p in d['pupils']}
    assert by_id['p01']['partner_pid'] == CODES['p02'] and by_id['p02']['partner_pid'] == CODES['p01']
    print('class list pid OK')

# pupil-facing live pages must not load the names helper
for t in ('live_assess.html', 'live_bee_pupil.html', 'live_error.html'):
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates', t)).read()
    assert 'extends' not in src and 'names-file.js' not in src, t
flask_app.jinja_env.get_template('class_manager.html')
print('ALL OK')

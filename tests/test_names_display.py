"""Run with plain python:  python3 tests/test_names_display.py
Proves the shared label helper and that the staff-facing pages/JSON never
carry pupil names. Fake names only. Needs jinja2 and flask (already deps)."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('GITHUB_TOKEN', 'x')

from names_display import label_list, labels_for_pupils

# ── label helper ─────────────────────────────────────────────────────────────
assert label_list(['Innes McLean']) == ['IM']
assert label_list([('Innes', 'McLean')]) == ['IM']
assert label_list(['Anna Taylor-Smith']) == ['AT']
assert label_list(['Anna Mary Jones']) == ['AJ']             # last word of surname
r = label_list([('Innes', 'McLean'), ('Ivor', 'McLeod')])
assert r == ['InMc', 'IvMc'], r
assert label_list([('Amy', 'Tay'), ('Amy', 'Tay'), ('Amy', 'Tay')]) == ['AT', 'AT 2', 'AT 3']
assert label_list(['Zed']) == ['Ze']
assert label_list([("Ann", "O'Neil")]) == ['AO']
three = label_list([('Innes', 'McLean'), ('Innis', 'McLeod')])
assert three[0] != three[1] and three[0].startswith('Inne') and three[1].startswith('Inni'), three
assert label_list([('Ines', 'McLean'), ('Inna', 'McLean')]) == ['IneMcL', 'InnMcL']
assert labels_for_pupils([{'id': 'p01', 'first': 'Innes', 'last': 'McLean'},
                          {'id': 'p02', 'first': 'Ivor', 'last': 'McLeod'}]) == {'p01': 'InMc', 'p02': 'IvMc'}
print('label helper OK')

FAKE = [
    {'id': 'p01', 'first': 'Zebulon', 'last': 'Quillfeather', 'upn': 'A123456789012', 'cls': 'IM'},
    {'id': 'p02', 'first': 'Zara', 'last': 'Quimby', 'upn': 'A123456789013', 'cls': 'IM'},
    {'id': 'p03', 'first': 'Wilbur', 'last': 'Fenwick-Dribble', 'upn': 'A123456789014', 'cls': 'IM'},
]
NAME_BITS = ['Zebulon', 'Quillfeather', 'Zara', 'Quimby', 'Wilbur', 'Fenwick', 'Dribble', 'A1234567890']


def assert_clean(text, where):
    for bit in NAME_BITS:
        assert bit not in text, f'{where}: leaked {bit!r}'


def walk_keys(o, path=''):
    if isinstance(o, dict):
        for k, v in o.items():
            assert k not in ('first', 'last', 'name', 'upn'), f'forbidden key {path}/{k}'
            walk_keys(v, f'{path}/{k}')
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk_keys(v, f'{path}[{i}]')

# ── Flask app with monkeypatched data layer ─────────────────────────────────
import data_manager
import app as appmod
flask_app = appmod.app
flask_app.config['TESTING'] = True

import copy
def fake_class(cid):
    ps = [dict(copy.deepcopy(p), group='main', tt_set='2', tt_mode='x', pair_id='', mastered=[], word_pos=0,
               pair_colour='', table='1') for p in FAKE]
    ps[0]['pair_id'] = 'p02'; ps[1]['pair_id'] = 'p01'
    return {'pupils': ps}

import routes.dashboard as rdash, routes.bee as rbee, routes.tt as rtt, routes.class_manager as rcm

# dashboard ------------------------------------------------------------------
rows = [data_manager._pupil_row(p) for p in fake_class('x')['pupils']]
rdash.load_dashboard = lambda cls: {'rows': rows, 'tt_dist': {}, 'stats': {'total': 3, 'main': 3, 'revision': 0, 'paired': 2, 'avg_mastered': 0}}
rdash.lowest_confidence_key_spellings = lambda *a, **k: []
rdash.load_learners = lambda cls: fake_class('x')['pupils']
rdash.get_class_options_for_year = lambda yr: [('Y4_all', 'All')]

# bee ------------------------------------------------------------------------
def fake_bee(cid, week):
    ps = [{'id': p['id'], 'first': p['first'], 'last': p['last'], 'cls': 'IM', 'file_cls': cid, 'group': 'main',
           'is_phonics': False, 'gpc_label': '', 'phonics_words': [], 'rule_label': '', 'words': ['about'],
           'marked_key': [], 'marked_rule': [], 'words_updated_at': ''} for p in fake_class(cid)['pupils']]
    return ps, {'main': '-', 'lessons': [], 'rule_groups': {}, 'hl_words': [], 'week': 'T1W1', 'year_group': 'Y4'}, 'T1W1'
rbee.load_bee_pupils = fake_bee
rbee.get_bee_weeks = lambda yr: ([], 'T1W1')
rbee.week_needing_marking = lambda cls, cur: 'T1W1'
rbee._resolve_classes = lambda cls: ['4IM']
rbee.get_class_options_for_year = lambda yr: [('Y4_all', 'All')]

# tt -------------------------------------------------------------------------
def fake_tt(cls):
    return [{'id': p['id'], 'name': f"{p['first']} {p['last']}", 'first': p['first'], 'last': p['last'],
             'tt_set': '2', 'tt_mode': 'x', 'label': '×2', 'cls': 'IM'} for p in FAKE]
rtt.load_tt_pupils = fake_tt
rtt.get_class_options_for_year = lambda yr: [('Y4_all', 'All')]

with flask_app.test_client() as c:
    with c.session_transaction() as s:
        s['year_group'] = '4'
        s['authed'] = True
    for url in ('/dashboard', '/spelling-bee', '/tt', '/api/tt/data'):
        r = c.get(url)
        body = r.get_data(as_text=True)
        assert r.status_code == 200, (url, r.status_code, body[:300])
        assert_clean(body, url)
        print(url, 'OK, no names;', 'labels seen:', [l for l in ('ZQ', 'ZeQ', 'ZQu', 'WF', 'ZeQuil') if l in body][:4])
    walk_keys(c.get('/api/tt/data').get_json())

    # class manager -----------------------------------------------------------
    rcm._load_class_file = lambda cid: (fake_class(cid), 'sha')
    rcm.ALL_CLASSES = ['4IM']
    rcm.reading_ladder_for_year = lambda y: ['4', '3', 'phonics']
    d = c.get('/api/class/list?cls=4IM').get_json()
    assert d['ok'], d
    walk_keys(d)
    assert_clean(json.dumps(d), '/api/class/list')
    assert all('label' in p for p in d['pupils']) and all('label' in p for p in d['all_pupils'])
    print('class list labels:', [p['label'] for p in d['pupils']], [p['partner_label'] for p in d['pupils']])

    # update endpoint works with ids only and never touches first/last
    saved = {}
    rcm._save_class_file = lambda cid, obj, sha, msg: saved.update(obj=obj) or True
    r = c.post('/api/class/pupil/update', json={'cls': '4IM', 'pupil_id': 'p01', 'changes': {'table': '7', 'first': '', 'last': ''}})
    assert r.get_json()['ok']
    p1 = next(p for p in saved['obj']['pupils'] if p['id'] == 'p01')
    assert p1['first'] == 'Zebulon' and p1['last'] == 'Quillfeather' and p1['table'] == '7'
    print('update keeps stored names; table saved')

    # pair_bulk error text must carry labels only
    r = c.post('/api/class/pair_bulk', json={'cls_id': '4IM', 'assignments': {'p01': '1', 'p02': '1', 'p03': '1'}}).get_json()
    assert not r['ok']; assert_clean(json.dumps(r), 'pair_bulk'); print('pair_bulk error:', r['error'])

# roster sync summary -------------------------------------------------------
summary = {'ok': True, 'roster_count': 3, 'when': 'x', 'applied': True, 'aborted': None, 'meta': {'added': 1},
           'updated': [{'cls': '4IM', 'id': 'p01'}],
           'renamed': [{'cls': '4IM', 'id': 'p01', 'was': 'Zebulon Quill', 'now': 'Zebulon Quillfeather'}],
           'upn_attached': [{'cls': '4IM', 'name': 'Zara Quimby', 'upn': 'A123456789013'}],
           'added': [{'cls': '4IM', 'id': 'p04', 'name': 'Wilbur Fenwick-Dribble', 'upn': 'A123456789014'}],
           'removed': [{'cls': '4IM', 'id': 'p05', 'name': 'Zara Quimby', 'upn': 'A123456789013'}],
           'unmatched': [{'cls': '4IM', 'name': 'Zebulon Quillfeather', 'upn': '', 'note': 'n'}],
           'skipped_new': [{'name': 'Zebulon Quillfeather', 'class': '9X', 'note': 'n'}]}
out = rcm._roster_summary_for_browser(summary)
walk_keys(out); assert_clean(json.dumps(out), 'roster-sync')
assert out['added'][0]['label'] == 'WF' and out['removed'][0]['label'] == 'ZQ'
print('roster-sync summary OK:', out['added'], out['removed'])

# template parse ------------------------------------------------------------
import jinja2
env = flask_app.jinja_env
for t in ('dashboard.html', 'bee.html', 'tt_check.html', 'class_manager.html'):
    env.get_template(t)
print('templates parse OK')
print('ALL OK')

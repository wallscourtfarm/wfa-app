"""Run with plain python:  python3 tests/test_seat_tables.py
Proves /api/class/tables (seating plan import): one save, only 'table' changes,
bad input refused, nothing saved when nothing changed. Fake data only."""
import os, sys, copy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('GITHUB_TOKEN', 'x')

import app as appmod
import routes.class_manager as cm

BASE = {'pupils': [
    {'id': 'p01', 'first': 'Zeb', 'last': 'Qui', 'table': '4', 'tt_set': '2', 'mastered': ['about']},
    {'id': 'p02', 'first': 'Zar', 'last': 'Quy', 'table': '', 'tt_set': '3', 'mastered': []},
    {'id': 'p03', 'first': 'Wil', 'last': 'Fen', 'table': '7', 'tt_set': '2', 'mastered': []},
]}
store, saves = {}, []

def fake_load(cid):
    return (copy.deepcopy(store[cid]), 'sha1') if cid in store else (None, None)

def fake_save(cid, obj, sha, msg):
    saves.append((cid, msg)); store[cid] = copy.deepcopy(obj); return True

cm._load_class_file, cm._save_class_file = fake_load, fake_save
c = appmod.app.test_client()

def post(tables, cls='5IM'):
    return c.post('/api/class/tables', json={'cls': cls, 'tables': tables}).get_json()

store['5IM'] = copy.deepcopy(BASE)
r = post({'p01': '2', 'p02': '1', 'p03': ''})
assert r == {'ok': True, 'changed': 3}, r
assert len(saves) == 1 and 'Zeb' not in saves[0][1]
ps = {p['id']: p for p in store['5IM']['pupils']}
assert [ps[i]['table'] for i in ('p01', 'p02', 'p03')] == ['2', '1', '']
for p in store['5IM']['pupils']:                       # nothing but table changed
    b = next(x for x in BASE['pupils'] if x['id'] == p['id'])
    assert {k: v for k, v in p.items() if k != 'table'} == {k: v for k, v in b.items() if k != 'table'}
print('save OK: one commit, only table changed')

r = post({'p01': '2', 'p02': '1', 'p03': ''})
assert r == {'ok': True, 'changed': 0} and len(saves) == 1
print('no change -> no save OK')

for bad in ({'p01': '1', 'p02': '1'}, {'p01': 'x'}, {'p01': '1234'}, {'p01': 3}, {}, {'zz': '1'}):
    r = post(bad)
    assert r['ok'] is False, (bad, r)
assert post({'p01': '1'}, cls='NOPE')['ok'] is False
assert len(saves) == 1
print('bad input refused OK')
print('ALL OK')

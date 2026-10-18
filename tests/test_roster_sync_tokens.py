"""Roster sync with UPN at rest: the roster's `upn` is an opaque token, so class pupils must be matched on their
pupil code and nobody may be removed, renamed to a token or given a UPN. Run: python3 tests/test_roster_sync_tokens.py
Fake data only."""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('GITHUB_TOKEN', 'x')
import roster_sync

STORE = {'data/classes/5IM.json': {'class_id': '5IM', 'pupils': [
    {'id': 'p01', 'first': 'Inn', 'last': 'McL', 'cls': 'IM', 'upn': 'A123456789012', 'pupil_id': 'p_aaaaaaaaaa', 'mastered': ['x']},
    {'id': 'p02', 'first': 'Ann', 'last': 'Lee', 'cls': 'IM', 'upn': '', 'pupil_id': 'p_bbbbbbbbbb', 'mastered': []},
    {'id': 'p03', 'first': 'Gone', 'last': 'Child', 'cls': 'IM', 'upn': 'A123456789099', 'pupil_id': 'p_gonegone22', 'mastered': []},
]}}
ROSTER = [
    {'upn': 'u_' + 'a' * 32, 'pupilId': 'p_aaaaaaaaaa', 'first': 'Inn', 'last': 'McL', 'class': '5IM', 'yearGroup': 'Y5'},
    {'upn': 'u_' + 'b' * 32, 'pupilId': 'p_bbbbbbbbbb', 'first': 'Ann', 'last': 'Lee', 'class': '5IM', 'yearGroup': 'Y5'},
    {'upn': 'u_' + 'c' * 32, 'pupilId': 'p_cccccccccc', 'first': 'New', 'last': 'Kid', 'class': '5IM', 'yearGroup': 'Y5'},
]
store = copy.deepcopy(STORE)
roster_sync._gh_get = lambda path: (copy.deepcopy(store[path]), 'sha1') if path in store else (None, None)
puts = []
roster_sync._gh_put = lambda path, obj, sha, msg: (store.__setitem__(path, copy.deepcopy(obj)), puts.append(path), True)[2]
roster_sync.fetch_classes = lambda: []
roster_sync.MIN_ROSTER_RATIO = 0.0
roster_sync.ALL_CLASSES = ['5IM']
res = roster_sync.sync_roster(apply=False, remove_leavers=True, roster=ROSTER)
assert res['ok'], res
removed = [r['id'] for r in res['removed']]
assert removed == ['p03'], removed                         # only the child whose code is NOT on the roster
assert not res['upn_attached'], res['upn_attached']        # a token is never written into a class file
assert [a['name'] for a in res['added']] == ['New Kid'], res['added']
assert not res['renamed'], res['renamed']                  # same stubs on both sides: no churn
res2 = roster_sync.sync_roster(apply=True, remove_leavers=True, roster=ROSTER)
pupils = {p['pupil_id']: p for p in store['data/classes/5IM.json']['pupils']}
assert 'p_aaaaaaaaaa' in pupils and 'p_bbbbbbbbbb' in pupils and 'p_gonegone22' not in pupils
assert pupils['p_aaaaaaaaaa']['upn'] == 'A123456789012' and pupils['p_aaaaaaaaaa']['mastered'] == ['x']     # untouched
new = [p for p in pupils.values() if p.get('pupil_id') == 'p_cccccccccc']
assert len(new) == 1 and new[0]['upn'] == ''
assert 'u_' + 'a' * 32 not in str(store), 'a UPN token reached a class file'
print('ALL OK')

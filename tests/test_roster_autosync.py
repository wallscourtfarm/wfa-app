"""Automatic roster sync: syncs only when the roster has changed and settled, records the roster fingerprint so it
does not repeat, leaves big removals for the button, and survives a failed roster fetch.
Run: python3 tests/test_roster_autosync.py   Fake data only, no network."""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('GITHUB_TOKEN', 'x')
import roster_sync
import roster_autosync

CLASS = {'class_id': '5IM', 'pupils': [
    {'id': 'p01', 'first': 'Inn', 'last': 'McL', 'cls': 'IM', 'pupil_id': 'p_aaaaaaaaaa', 'mastered': ['x']},
    {'id': 'p02', 'first': 'Ann', 'last': 'Lee', 'cls': 'IM', 'pupil_id': 'p_bbbbbbbbbb', 'mastered': []},
]}
ROSTER = [
    {'upn': 'u_' + 'a' * 32, 'pupilId': 'p_aaaaaaaaaa', 'first': 'Inn', 'last': 'McL', 'class': '5IM', 'yearGroup': 'Y5'},
    {'upn': 'u_' + 'b' * 32, 'pupilId': 'p_bbbbbbbbbb', 'first': 'Ann', 'last': 'Lee', 'class': '5IM', 'yearGroup': 'Y5'},
]
NEW_KID = {'upn': 'u_' + 'c' * 32, 'pupilId': 'p_cccccccccc', 'first': 'New', 'last': 'Kid', 'class': '5IM', 'yearGroup': 'Y5'}

store = {'data/classes/5IM.json': copy.deepcopy(CLASS)}
puts = []
roster = {'now': copy.deepcopy(ROSTER)}
roster_sync._gh_get = lambda path: (copy.deepcopy(store[path]), 'sha1') if path in store else (None, None)
roster_sync._gh_put = lambda path, obj, sha, msg: (store.__setitem__(path, copy.deepcopy(obj)), puts.append(path), True)[2]
roster_sync.fetch_roster = lambda: copy.deepcopy(roster['now'])
roster_sync.fetch_classes = lambda: [{'display': '5IM', 'teacherInitials': 'IM'}]
roster_sync.MIN_ROSTER_RATIO = 0.0
roster_sync.ALL_CLASSES = ['5IM']

# fingerprint ignores order, notices a change
fp = roster_sync.roster_fingerprint
assert fp(ROSTER, []) == fp(list(reversed(ROSTER)), [])
assert fp(ROSTER, []) != fp(ROSTER + [NEW_KID], [])
assert fp(ROSTER, [{'display': '5IM', 'teacherInitials': 'IM'}]) != fp(ROSTER, [{'display': '5IM', 'teacherInitials': 'XX'}])
print('fingerprint OK')

# no meta yet: first sight waits, second sight syncs and records the fingerprint
st = roster_autosync.new_state()
assert roster_autosync.check_once(st) == 'waiting' and puts == []
assert roster_autosync.check_once(st) == 'synced', puts
meta = store[roster_sync.META_PATH]
assert meta['trigger'] == 'auto' and meta['roster_hash'] == fp(ROSTER, roster_sync.fetch_classes())
assert store['data/classes/5IM.json']['teacher'] == 'IM'
print('first sync OK')

# nothing changed: nothing written
puts.clear()
for _ in range(3):
    assert roster_autosync.check_once(st) == 'up-to-date'
assert puts == []
print('unchanged roster writes nothing OK')

# a new arrival: waits one check, then adds the child with their code
roster['now'] = ROSTER + [NEW_KID]
assert roster_autosync.check_once(st) == 'waiting' and puts == []
assert roster_autosync.check_once(st) == 'synced'
codes = [p['pupil_id'] for p in store['data/classes/5IM.json']['pupils']]
assert 'p_cccccccccc' in codes and 'mastered' in store['data/classes/5IM.json']['pupils'][0]
assert roster_autosync.check_once(st) == 'up-to-date'
print('new arrival synced OK')

# a roster still changing between checks never syncs part-way
puts.clear()
roster['now'] = ROSTER
assert roster_autosync.check_once(st) == 'waiting'
roster['now'] = [ROSTER[0]]
assert roster_autosync.check_once(st) == 'waiting' and puts == []
print('unsettled roster waits OK')

# the button's sync also records the fingerprint, so the automatic one does not repeat it
roster['now'] = copy.deepcopy(ROSTER)
roster_sync.sync_roster(apply=True)
assert store[roster_sync.META_PATH]['trigger'] == 'button'
puts.clear()
assert roster_autosync.check_once(roster_autosync.new_state()) == 'up-to-date' and puts == []
print('button sync recognised OK')

# too many removals: dry run only, nothing written, not retried
big = [{'id': f'p{i:02}', 'first': 'A', 'last': f'B{i}', 'cls': 'IM', 'pupil_id': f'p_gone{i:06}', 'mastered': []}
       for i in range(roster_autosync.MAX_AUTO_REMOVALS + 1)]
store['data/classes/5IM.json']['pupils'] += big
roster['now'] = ROSTER + [NEW_KID]
st = roster_autosync.new_state()
puts.clear()
assert roster_autosync.check_once(st) == 'waiting'
assert roster_autosync.check_once(st) == 'skipped-too-many-removals' and puts == []
assert roster_autosync.check_once(st) == 'already-tried' and puts == []
print('big removal left for the button OK')

# roster fetch failure: no crash, nothing written
def boom():
    raise RuntimeError('down')
roster_sync.fetch_roster = boom
assert roster_autosync.check_once(st) == 'fetch-failed' and puts == []
print('fetch failure OK')

# off unless on Railway or switched on
for k in ('ROSTER_AUTO_SYNC', 'RAILWAY_ENVIRONMENT_NAME'):
    os.environ.pop(k, None)
assert roster_autosync.start() is False
os.environ['RAILWAY_ENVIRONMENT_NAME'] = 'production'
os.environ['ROSTER_AUTO_SYNC'] = '0'
assert roster_autosync.start() is False
print('start guard OK')
print('ALL OK')

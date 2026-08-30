"""
One-off: apply the first roster sync to the spelling-homelearning class
files, with progress printed per commit.

    python3 scripts/run_roster_sync.py
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import roster_sync  # noqa: E402


def gh_token():
    t = os.environ.get('GITHUB_TOKEN')
    if t:
        return t
    r = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True)
    if r.returncode == 0:
        return r.stdout.strip()
    sys.exit('No GitHub token found. Run: gh auth login')


os.environ['GITHUB_TOKEN'] = gh_token()
# roster_sync reads the token at import time — reload after setting it
import importlib  # noqa: E402
importlib.reload(roster_sync)

orig_put = roster_sync._gh_put


def put(path, obj, sha, msg):
    ok = orig_put(path, obj, sha, msg)
    print(f"  {'✅' if ok else '❌'} committed {path}: {msg}", flush=True)
    return ok


roster_sync._gh_put = put

print('Fetching roster from shared-sync bus…', flush=True)
roster = roster_sync.fetch_roster()
print(f'Roster: {len(roster)} pupils. Matching…', flush=True)

r = roster_sync.sync_roster(apply=True, roster=roster)

print('\n── RESULT ──')
print(f"ok: {r['ok']}   aborted: {r['aborted']}")
print(f"name refreshes: {len(r['updated'])} (renames: {len(r['renamed'])})")
for x in r['renamed']:
    print(f"   {x['cls']} {x['id']}: {x['was']}  →  {x['now']}")
print(f"UPNs attached: {len(r['upn_attached'])}")
print(f"added: {len(r['added'])}", r['added'] or '')
print(f"removed: {len(r['removed'])}", r['removed'] or '')
print(f"unmatched: {len(r['unmatched'])}", r['unmatched'] or '')
print(f"skipped_new: {len(r['skipped_new'])}", r['skipped_new'] or '')
print(f"\nmeta: {json.dumps(r['meta'])}")
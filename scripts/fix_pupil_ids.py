"""
fix_pupil_ids.py
----------------
One-off: makes every pupil id globally unique across the class files of
wallscourtfarm/spelling-homelearning.

The 2026-27 rollover re-used old pupil ids (pending-rolled Y3/Y5 pupils
and fresh imports both drew from low p-numbers), so 36 ids are shared by
two or three DIFFERENT children across classes. Damage: _all_pupils_map()
is global and last-wins, so partner-name lookups for Y5 pairings resolve
to the wrong pupil; homophone/insight joins by id can hit the wrong twin.

Rules:
  - Keep the first occurrence of each id (class order per
    YEAR_GROUP_CLASSES, then file order); renumber later occurrences with
    fresh ids continuing from the global max (p280+).
  - Remap pair_id references that point to a renamed pupil within the
    same class file (all pair refs are intra-class — verified).
  - Sessions and results files embed their own id+name snapshot, so
    historical data is not touched.

Usage:
    python3 scripts/fix_pupil_ids.py            # dry run
    python3 scripts/fix_pupil_ids.py --apply    # commit to GitHub
"""

import base64
import json
import os
import subprocess
import sys
import time
from urllib import request as urlreq
from urllib.error import HTTPError

# ── Config ───────────────────────────────────────────────────────────────────
DATA_REPO = "wallscourtfarm/spelling-homelearning"
BRANCH = "main"
BASE_URL = f"https://api.github.com/repos/{DATA_REPO}/contents"
AUDIT_DIR = os.path.expanduser("~/Desktop/Claude Assets/upn-audit")

YEAR_GROUP_CLASSES = {
    "1": ["1ER", "1JS"],
    "2": ["2MY", "2JH"],
    "3": ["3JW", "3WU"],
    "4": ["4CC", "4RB"],
    "5": ["5LS", "5IM"],
    "6": ["6JM", "6SD"],
}


def get_token():
    t = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if t:
        return t
    r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    if r.returncode == 0:
        return r.stdout.strip()
    sys.exit("No GitHub token found. Run: gh auth login")


TOKEN = get_token()
HEADERS = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}


def gh_get(path):
    r = urlreq.Request(f"{BASE_URL}/{path}?ref={BRANCH}", headers=HEADERS)
    try:
        with urlreq.urlopen(r, timeout=15) as resp:
            d = json.loads(resp.read().decode())
    except HTTPError as e:
        if e.code == 404:
            return None, None
        raise
    return json.loads(base64.b64decode(d["content"]).decode()), d["sha"]


def gh_put(path, data, sha, message):
    body = {
        "message": message,
        "content": base64.b64encode(
            json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        ).decode(),
        "sha": sha,
        "branch": BRANCH,
    }
    req = urlreq.Request(f"{BASE_URL}/{path}", data=json.dumps(body).encode(),
                         headers={**HEADERS, "Content-Type": "application/json"},
                         method="PUT")
    with urlreq.urlopen(req, timeout=30) as resp:
        resp.read()


def main():
    apply = "--apply" in sys.argv[1:]
    class_order = [c for classes in YEAR_GROUP_CLASSES.values() for c in classes]

    print("Loading class files ...")
    files = {}
    for cls_id in class_order:
        obj, sha = gh_get(f"data/classes/{cls_id}.json")
        if obj is None:
            print(f"  {cls_id}: MISSING")
            continue
        files[cls_id] = {"obj": obj, "sha": sha}
    n_pupils = sum(len(f["obj"].get("pupils", [])) for f in files.values())
    print(f"  {len(files)} classes, {n_pupils} pupils")

    # Pass 1: collisions + fresh id assignment (class order, then file order)
    first_owner = {}   # id -> class of first occurrence
    renames = []       # (cls_id, pupil, old_id, new_id)
    max_existing = max(
        (int(p["id"][1:]) for f in files.values() for p in f["obj"].get("pupils", [])
         if p.get("id", "").startswith("p") and p["id"][1:].isdigit()),
        default=0,
    )
    next_n = max_existing

    for cls_id in class_order:
        if cls_id not in files:
            continue
        for p in files[cls_id]["obj"].get("pupils", []):
            pid = p.get("id", "")
            if pid in first_owner:
                next_n += 1
                renames.append((cls_id, p, pid, f"p{next_n}"))
            else:
                first_owner[pid] = cls_id

    if not renames:
        print("No collisions — nothing to do.")
        return

    print(f"\n{len(renames)} pupils renumbered (global max was p{max_existing}):")
    for cls_id, p, old, new in renames:
        print(f"  {cls_id}  {p.get('first','')} {p.get('last','')}:  {old} -> {new}  "
              f"(upn {p.get('upn') or '—'})")

    # Pass 2: apply renames, then remap same-file pair_id references
    per_class_renames = {}
    for cls_id, p, old, new in renames:
        per_class_renames.setdefault(cls_id, {})[old] = new

    pair_refixed = 0
    changed_classes = []
    for cls_id, f in files.items():
        m = per_class_renames.get(cls_id, {})
        if not m:
            continue
        for p in f["obj"].get("pupils", []):
            if p["id"] in m:
                p["id"] = m[p["id"]]
        for p in f["obj"].get("pupils", []):
            if p.get("pair_id") in m and p["pair_id"] != p["id"]:
                p["pair_id"] = m[p["pair_id"]]
                pair_refixed += 1
        changed_classes.append(cls_id)
        if apply:
            print(f"Committing {cls_id} ...")
            gh_put(f"data/classes/{cls_id}.json", f["obj"], f["sha"],
                   "Fix duplicate pupil ids: renumber collisions to make ids globally unique")
            time.sleep(1.5)

    # Audit trail (private location — contains pupil names)
    os.makedirs(AUDIT_DIR, exist_ok=True)
    audit = [
        {"class": cls_id, "first": p.get("first"), "last": p.get("last"),
         "old_id": old, "new_id": new, "upn": p.get("upn")}
        for cls_id, p, old, new in renames
    ]
    out = os.path.join(AUDIT_DIR, "pupil_id_renames.json")
    with open(out, "w") as fp:
        json.dump(audit, fp, indent=2, ensure_ascii=False)
    print(f"\nPair_id references remapped: {pair_refixed}")
    print(f"Audit log written to {out}")
    if not apply:
        print("\nDry run — nothing written. Add --apply to commit.")


if __name__ == "__main__":
    main()
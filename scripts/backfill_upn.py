"""
backfill_upn.py
---------------
One-off (rerunnable): writes the UPN from the school roster (shared-sync
getPupils — the Bromcom-fed master sheet) onto every pupil in the
class JSONs of wallscourtfarm/spelling-homelearning.

Matching is EXACT name only (case/whitespace-insensitive first+last).
Anything that doesn't match exactly is reported, never guessed internally:

  - unmatched pupil    — in class files, no roster row with that exact name
  - unmatched roster   — roster row with no class-file pupil
  - duplicate names    — same name twice on either side (ambiguous)
  - fuzzy suggestion   — likely rename (e.g. "Fredrick" vs "Freddie"): only
                         in the report; a --fuzzy file can confirm them

Also reports class-code drift (e.g. roster 4CC vs file 4CK) and duplicate
pupil ids within one class file (pre-existing data bugs — reported, not
touched).

Usage:
    python3 scripts/backfill_upn.py            # dry run: report only
    python3 scripts/backfill_upn.py --apply    # commit upn backfills to GitHub
    python3 scripts/backfill_upn.py --apply fuzzy.json
    # fuzzy.json: {"4CK": {"frederick allford": "E8032…", …}} — normalized
    # "first last" keys (as printed by the FUZZY report); one UPN per name.
"""

import base64
import json
import os
import subprocess
import sys
import time
import unicodedata
from urllib import request as urlreq
from urllib.error import HTTPError, URLError

# ── Config ───────────────────────────────────────────────────────────────────
DATA_REPO = "wallscourtfarm/spelling-homelearning"
BRANCH = "main"
BASE_URL = f"https://api.github.com/repos/{DATA_REPO}/contents"

# Shared-sync deployment all staff-tools clients use (token ships in the
# client HTML too — same light deterrence, not a secret).
ROSTER_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbxHg89VK1uqbWAJcqruqJFjEaavdWN74eB1KS-U_cMr75oVsBVZSi2X38l018oOYW7-4w/exec"
    "?action=getPupils&token=2013"
)

YEAR_GROUP_CLASSES = {
    "1": ["1ER", "1JS"],
    "2": ["2MY", "2JH"],
    "3": ["3JW", "3WU"],
    "4": ["4CK", "4RB"],
    "5": ["5LS", "5IM"],
    "6": ["6JM", "6SD"],
}

# Class codes the roster may use for a file that lives under a different name
# in the repo (rename observed in Bromcom). Key = roster code, value = file.
CLASS_ALIASES = {
    "4CC": "4CK",
}


# ── Small helpers ────────────────────────────────────────────────────────────
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
    import base64 as b64

    req = urlreq.Request(
        f"{BASE_URL}/{path}",
        data=json.dumps(
            {
                "message": message,
                "content": b64.b64encode(
                    json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
                ).decode(),
                "sha": sha,
                "branch": BRANCH,
            }
        ).encode(),
        headers={**HEADERS, "Content-Type": "application/json"},
        method="PUT",
    )
    with urlreq.urlopen(req, timeout=30) as resp:
        resp.read()


def fetch_roster():
    for attempt in range(3):
        try:
            with urlreq.urlopen(ROSTER_URL, timeout=30) as resp:
                d = json.loads(resp.read().decode())
            pupils = d.get("pupils", [])
            if pupils:
                return pupils
        except (HTTPError, URLError) as e:
            print(f"  roster fetch attempt {attempt + 1} failed: {e}")
            time.sleep(2)
    sys.exit("Could not fetch the roster from shared-sync getPupils")


def name_key(first, last):
    """Case/accent/whitespace-insensitive full-name key."""
    first = unicodedata.normalize("NFKD", first or "").encode("ascii", "ignore").decode()
    last = unicodedata.normalize("NFKD", last or "").encode("ascii", "ignore").decode()
    return " ".join((first + " " + last).split()).lower()


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    fuzzy_path = None
    apply = False
    args = list(sys.argv[1:])
    if "--apply" in args:
        apply = True
        args.remove("--apply")
    if args:
        fuzzy_path = args[0]

    print("Fetching roster from shared-sync getPupils ...")
    roster = fetch_roster()
    print(f"  {len(roster)} active pupils from roster ({roster[0].get('source')} source)")

    # Roster name -> roster pupil (flag duplicates)
    roster_by_name = {}
    for r in roster:
        k = name_key(r["first"], r["last"])
        roster_by_name.setdefault(k, []).append(r)
    dup_roster = {k for k, v in roster_by_name.items() if len(v) > 1}

    # Load all class files
    all_classes = sorted(c for classes in YEAR_GROUP_CLASSES.values() for c in classes)
    print(f"\nLoading {len(all_classes)} class files from GitHub ...")
    class_files = {}
    for cls_id in all_classes:
        obj, sha = gh_get(cls_path(cls_id))
        if obj is None:
            print(f"  {cls_id}: MISSING — skipped")
            continue
        class_files[cls_id] = {"obj": obj, "sha": sha, "changed": False}
        print(f"  {cls_id}: {len(obj.get('pupils', []))} pupils")

    # ── Match ────────────────────────────────────────────────────────────────
    report = {
        "matched": 0,
        "already_upn": 0,
        "unmatched_pupils": [],   # class-file pupils with no roster hit
        "unmatched_roster": [],   # roster kids with no class-file hit
        "ambiguous": [],          # same name twice anywhere
        "class_drift": [],        # file says X, roster says Y
        "fuzzy": [],              # rename candidates (report + --fuzzy file)
    }
    fuzzy_applied = {}
    if fuzzy_path:
        with open(fuzzy_path) as f:
            fuzzy_applied = json.load(f)  # {cls_id: {name_key: upn}}

    # duplicate-id detection (within one class file) — pre-existing bug check
    dup_ids = []

    for cls_id, cf in class_files.items():
        seen_ids = {}
        for p in cf["obj"].get("pupils", []):
            k = name_key(p.get("first"), p.get("last"))
            hits = roster_by_name.get(k, [])
            seen_ids[p.get("id", "")] = seen_ids.get(p.get("id", ""), 0) + 1
            if fuzzy_applied.get(cls_id, {}).get(k):
                p["upn"] = fuzzy_applied[cls_id][k]
                cf["changed"] = True
                report["matched"] += 1
                continue
            if len(hits) > 1:
                report["ambiguous"].append({"class": cls_id, "pupil": p.get("id"), "name": k})
                continue
            if not hits:
                report["unmatched_pupils"].append(
                    {"class": cls_id, "id": p.get("id"), "name": f"{p.get('first')} {p.get('last')}"}
                )
                # Fuzzy suggestion: same surname, first name shares ≥3 chars in order
                surj = k.rsplit(" ", 1)[-1] if " " in k else ""
                for rk, rhs in roster_by_name.items():
                    if len(rhs) != 1:
                        continue
                    rh = rhs[0]
                    if rh["yearGroup"] != f"Y{cls_id[0]}":
                        continue
                    rs = name_key(rh["first"], rh["last"]).rsplit(" ", 1)[-1]
                    if rs and rs == surj and _subseq(name_key(rh["first"], rh["last"]).split(" ")[0], k.split(" ")[0]):
                        report["fuzzy"].append(
                            {
                                "class": cls_id,
                                "pupil_id": p.get("id"),
                                "file_name": k,
                                "roster_name": name_key(rh["first"], rh["last"]),
                                "upn": rh["upn"],
                            }
                        )
                        break
                continue
            h = hits[0]
            if p.get("upn") and p["upn"] != h["upn"]:
                report["ambiguous"].append(
                    {"class": cls_id, "pupil": p.get("id"), "name": k,
                     "note": f"upn {p['upn']} != roster {h['upn']}"}
                )
                continue
            p["upn"] = h["upn"]
            report["matched"] += 1
            cf["changed"] = True
            # class drift check (roster code may be an alias or a rename)
            rcls = CLASS_ALIASES.get(h["class"], h["class"])
            if rcls != cls_id:
                report["class_drift"].append(
                    {"file": cls_id, "roster_class": h["class"], "pupil": k}
                )
        for dup_id, n in seen_ids.items():
            if n > 1:
                dup_ids.append(f"{cls_id}: id '{dup_id}' used by {n} pupils")

    report["duplicate_ids"] = dup_ids

    # roster pupils unused
    used_upns = {
        p.get("upn")
        for cf in class_files.values()
        for p in cf["obj"].get("pupils", [])
        if p.get("upn")
    }
    for r in roster:
        k = name_key(r["first"], r["last"])
        if r["upn"] not in used_upns and len(roster_by_name.get(k, [])) == 1:
            report["unmatched_roster"].append(
                {"roster_class": r["class"], "upn": r["upn"], "name": f"{r['first']} {r['last']}"}
            )

    for dn in sorted(dup_roster):
        names = ", ".join(f"{h['first']} {h['last']} ({h['class']})" for h in roster_by_name[dn])
        report["ambiguous"].append({"name": dn, "roster": names})

    # ── Report ───────────────────────────────────────────────────────────────
    print("\n══════════════ BACKFILL REPORT ══════════════")
    print(f"UPNs matched/written: {report['matched']}")
    if report["unmatched_pupils"]:
        print(f"\nIn class files but NOT in roster ({len(report['unmatched_pupils'])}):")
        for i in report["unmatched_pupils"]:
            print(f"  {i['class']}: {i['name']} ({i['id']})")
    if report["unmatched_roster"]:
        print(f"\nOn roster but NOT in any class file ({len(report['unmatched_roster'])}):")
        for i in report["unmatched_roster"]:
            print(f"  {i['roster_class']}: {i['name']} — UPN {i['upn']}")
    if report["fuzzy"]:
        print(f"\nSUGGESTED (rename? not applied without --fuzzy file) ({len(report['fuzzy'])}):")
        for i in report["fuzzy"]:
            print(f"  {i['class']}: '{i['file_name']}' -> '{i['roster_name']}' UPN {i['upn']}")
    if report["ambiguous"]:
        print(f"\nAMBIGUOUS ({len(report['ambiguous'])}):")
        for i in report["ambiguous"]:
            print(f"  {i}")
    if report["class_drift"]:
        cds = sorted({(i["file"], i["roster_class"]) for i in report["class_drift"]})
        print(f"\nCLASS CODE DRIFT ({len(cds)} files) — roster calls them {cds}")
    if report["duplicate_ids"]:
        print(f"\nDUPLICATE PUPIL IDS WITHIN A CLASS FILE ({len(report['duplicate_ids'])}) "
              f"— pre-existing bug, fix manually:")
        for i in report["duplicate_ids"]:
            print(f"  {i}")
    print("══════════════════════════════════════════════")

    if not apply:
        print("\nDry run — nothing written. Add --apply to commit the upn fields.")
        return

    changed = [c for c, cf in class_files.items() if cf["changed"]]
    if not changed:
        print("\nNothing to commit (no upn fields changed).")
        return
    for cls_id in changed:
        cf = class_files[cls_id]
        n = sum(1 for p in cf["obj"].get("pupils", []) if p.get("upn"))
        print(f"Committing {cls_id} ({n} pupils with upn) ...")
        gh_put(cls_path(cls_id), cf["obj"], cf["sha"],
               f"Backfill UPNs from Bromcom roster ({n}/{len(cf['obj'].get('pupils', []))} pupils)")
        time.sleep(1.5)  # stay well inside the GitHub contents-API rate limit
    print(f"\nDone — {len(changed)} class files updated.")


def _subseq(a, b):
    """True if every char of a appears in b in order (loose rename check)."""
    if not a:
        return False
    it = iter(b)
    return all(c in it for c in a)


# cls_path must mirror the repo layout used everywhere else
def cls_path(cls_id):
    return f"data/classes/{cls_id}.json"


if __name__ == "__main__":
    main()
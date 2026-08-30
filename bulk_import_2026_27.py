"""
bulk_import_2026_27.py
----------------------
Migrates spelling tracker data for 2026-27:

1. Pending Y3 pupils (rolled from Y2) → assigned to 3JW or 3WU per Bromcom
2. Pending Y5 pupils (rolled from Y4) → assigned to 5LS or 5IM per Bromcom
3. Y1, Y2, Y4, Y6 pupils added fresh from Bromcom xlsx

Writes directly to the wallscourtfarm/spelling-homelearning GitHub repo.

Usage:
    GH_TOKEN=<token> python3 bulk_import_2026_27.py
    # or just:
    python3 bulk_import_2026_27.py   (uses gh auth token automatically)
"""

import base64, json, os, subprocess, sys, time
from pathlib import Path
import openpyxl, requests

# ── Config ──────────────────────────────────────────────────────────────────
XLSX_PATH = Path.home() / "Downloads" / "Import to Claude from BromCom.xlsx"
DATA_REPO = "wallscourtfarm/spelling-homelearning"
BRANCH    = "main"
BASE_URL  = f"https://api.github.com/repos/{DATA_REPO}/contents"

def get_token():
    t = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if t: return t
    r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    if r.returncode == 0: return r.stdout.strip()
    sys.exit("No GitHub token found. Run: gh auth login")

TOKEN   = get_token()
HEADERS = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}

# New class IDs for 2026-27
YEAR_GROUP_CLASSES = {
    "1": ["1ER", "1JS"],
    "2": ["2MY", "2JH"],
    "3": ["3JW", "3WU"],
    "4": ["4CC", "4RB"],
    "5": ["5LS", "5IM"],
    "6": ["6JM", "6SD"],
}

# Old class files that hold the pending rolled pupils
OLD_PENDING = {
    "3": "Y3_RB",   # Y2 pupils rolled to Y3
    "5": "Y5_CK",   # Y4 pupils rolled to Y5
}

# ── GitHub helpers ───────────────────────────────────────────────────────────
def gh_get(path):
    r = requests.get(f"{BASE_URL}/{path}", headers=HEADERS, timeout=15)
    if r.status_code == 404: return None, None
    r.raise_for_status()
    d = r.json()
    return json.loads(base64.b64decode(d["content"]).decode()), d["sha"]

def gh_put(path, data, sha, message):
    content = base64.b64encode(json.dumps(data, indent=2, ensure_ascii=False).encode()).decode()
    body = {"message": message, "content": content, "branch": BRANCH}
    if sha: body["sha"] = sha
    r = requests.put(f"{BASE_URL}/{path}", headers=HEADERS, json=body, timeout=20)
    r.raise_for_status()
    time.sleep(0.4)  # avoid secondary rate limit

def cls_path(cls_id):
    return f"data/classes/{cls_id}.json"

def empty_class(cls_id, yr):
    return {
        "class_id":      cls_id,
        "class_display": f"Y{yr} — {cls_id.lstrip('0123456789')}",
        "year_group":    f"Y{yr}",
        "teacher":       "",
        "pupils":        [],
    }

def new_pupil(pid, first, last, cls_id, yr):
    return {
        "id":               pid,
        "first":            first,
        "last":             last,
        "cls":              cls_id.lstrip("0123456789"),
        "group":            "main",
        "tt_set":           "2",
        "tt_mode":          "x",
        "table":            "",
        "adapted_hl":       False,
        "language":         "",
        "pair_id":          "",
        "pair_colour":      "",
        "word_pos":         0,   # genuinely new pupil — start of the whole list, not the year's zone
        "mastered":         [],
        "rule_confidence":  {},
        "ss_user":          "",
        "ss_pass":          "",
        "homophone_mastered": [],
        "homophone_history":  {},
    }

# ── Read Bromcom xlsx ────────────────────────────────────────────────────────
def read_bromcom():
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h).strip() if h else "" for h in rows[0]]
    records = []
    for row in rows[1:]:
        rec = dict(zip(header, row))
        upn = str(rec.get("UPN", "") or "").strip()
        if not upn or upn == "[object Object]": continue
        first = str(rec.get("First Name", "") or "").strip()
        last  = str(rec.get("Last Name",  "") or "").strip()
        yg    = rec.get("Year Group")
        cls   = str(rec.get("Class", "") or "").strip()
        if not first or not yg or not cls: continue
        records.append({"first": first, "last": last, "yr": str(int(yg)), "cls": cls})
    wb.close()
    return records

# ── Next pupil ID (global across all classes) ────────────────────────────────
_pid_counter = [0]

def next_pid():
    _pid_counter[0] += 1
    return f"p{_pid_counter[0]:02d}"

def seed_counter_from_existing(class_files):
    """Find the highest existing pupil ID number across all loaded files."""
    max_n = 0
    for obj in class_files.values():
        if not obj: continue
        for p in obj.get("pupils", []):
            pid = p.get("id", "")
            if pid.startswith("p") and pid[1:].isdigit():
                max_n = max(max_n, int(pid[1:]))
    _pid_counter[0] = max_n

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("Reading Bromcom xlsx...")
    bromcom = read_bromcom()
    print(f"  {len(bromcom)} pupils")

    # Build name lookup: (first.lower, last.lower) -> {yr, cls}
    name_map = {}
    for rec in bromcom:
        key = (rec["first"].lower(), rec["last"].lower())
        name_map[key] = rec

    # ── Load all new class files (creating empties where needed) ──
    print("\nLoading new class files from GitHub...")
    class_data = {}   # cls_id -> (obj, sha)
    for yr, classes in YEAR_GROUP_CLASSES.items():
        for cls_id in classes:
            obj, sha = gh_get(cls_path(cls_id))
            if obj is None:
                print(f"  {cls_id}: not found — will create fresh")
                obj = empty_class(cls_id, yr)
                sha = None
            else:
                print(f"  {cls_id}: {len(obj.get('pupils', []))} existing pupils")
            class_data[cls_id] = (obj, sha)

    # ── Load old pending files ──
    print("\nLoading pending (rolled) class files...")
    pending_data = {}
    for yr, old_cls in OLD_PENDING.items():
        obj, sha = gh_get(cls_path(old_cls))
        pending_data[yr] = (old_cls, obj, sha)
        pending = [p for p in (obj or {}).get("pupils", []) if p.get("pending")]
        print(f"  {old_cls}: {len(pending)} pending pupils")

    # Seed the global counter
    all_objs = {cls: obj for cls, (obj, _) in class_data.items()}
    for _, obj, _ in pending_data.values():
        if obj:
            all_objs[f"_pending_{_}"] = obj
    seed_counter_from_existing(all_objs)
    print(f"\nStarting pupil IDs from p{_pid_counter[0]+1:02d}")

    # ── Step 1: Move pending pupils to their correct new classes ──
    print("\n── Assigning pending pupils ──")
    unmatched_pending = []
    for yr, (old_cls, old_obj, old_sha) in pending_data.items():
        if not old_obj: continue
        pending_pupils = [p for p in old_obj.get("pupils", []) if p.get("pending")]
        print(f"\n  {old_cls} → Y{yr} ({len(pending_pupils)} pending):")
        for pupil in pending_pupils:
            key = (pupil["first"].lower(), pupil["last"].lower())
            rec = name_map.get(key)
            if not rec:
                unmatched_pending.append(f"{pupil['first']} {pupil['last']} (was {old_cls})")
                continue
            new_cls = rec["cls"]
            if new_cls not in class_data:
                unmatched_pending.append(f"{pupil['first']} {pupil['last']} → unknown class {new_cls}")
                continue
            # Strip pending flag, update cls field
            pupil.pop("pending", None)
            pupil["cls"] = new_cls.lstrip("0123456789")
            class_data[new_cls][0]["pupils"].append(pupil)
            print(f"    {pupil['first']} {pupil['last']} → {new_cls}")

        # Clear the old file's pupils
        old_obj["pupils"] = [p for p in old_obj.get("pupils", []) if not p.get("pending")]

    # ── Step 2: Add fresh pupils for Y1, Y2, Y4, Y6 ──
    print("\n── Adding fresh year groups ──")
    skip_yrs = set(OLD_PENDING.keys())   # Y3 and Y5 already handled above
    for yr, classes in YEAR_GROUP_CLASSES.items():
        if yr in skip_yrs: continue
        yr_pupils = [r for r in bromcom if r["yr"] == yr]
        print(f"\n  Y{yr}: {len(yr_pupils)} pupils from Bromcom")
        for rec in yr_pupils:
            cls_id = rec["cls"]
            if cls_id not in class_data:
                print(f"    SKIP {rec['first']} {rec['last']} — unknown class {cls_id}")
                continue
            pid = next_pid()
            pupil = new_pupil(pid, rec["first"], rec["last"], cls_id, yr)
            class_data[cls_id][0]["pupils"].append(pupil)
            print(f"    {rec['first']} {rec['last']} → {cls_id} ({pid})")

    # ── Step 3: Save everything ──
    print("\n── Writing to GitHub ──")
    for cls_id, (obj, sha) in class_data.items():
        n = len(obj.get("pupils", []))
        print(f"  {cls_id}: {n} pupils... ", end="", flush=True)
        gh_put(cls_path(cls_id), obj, sha, f"2026-27 rollover: load {cls_id} ({n} pupils)")
        print("✓")

    # Clear old pending files
    for yr, (old_cls, old_obj, old_sha) in pending_data.items():
        if old_obj and old_sha:
            print(f"  {old_cls}: clearing pending pupils... ", end="", flush=True)
            gh_put(cls_path(old_cls), old_obj, old_sha, f"Clear pending after rollover ({old_cls})")
            print("✓")

    # ── Summary ──
    print("\n── Done ──")
    for cls_id, (obj, _) in class_data.items():
        print(f"  {cls_id}: {len(obj.get('pupils', []))} pupils")

    if unmatched_pending:
        print(f"\n⚠ Unmatched pending pupils ({len(unmatched_pending)}):")
        for u in unmatched_pending:
            print(f"  {u}")

if __name__ == "__main__":
    main()

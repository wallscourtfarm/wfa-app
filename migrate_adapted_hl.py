"""
One-off migration: replace the single adapted_hl boolean with independent
maths_level / reading_level fields on every pupil in every class.

  adapted_hl == True   -> maths_level = 'adapted', reading_level = 'phonics'
  adapted_hl == False/missing -> maths_level = 'standard', reading_level = 'standard'

This preserves every pupil's current home-learning experience exactly (maths
keeps its old adapted/standard split unchanged; a pupil who previously got
the old Y1/2-pitched "adapted" reading now gets the new most-adapted
"phonics" reading tier, the closest match). Innes then manually moves
individual pupils to reading_level='y3' via Class Manager where appropriate.

Usage:
    python3 migrate_adapted_hl.py            # dry run — prints what would change
    python3 migrate_adapted_hl.py --apply    # writes the changes to GitHub

Delete this file once the migration has been applied and verified.
"""
import sys
from routes.class_manager import _load_class_file, _save_class_file
from data_manager import ALL_CLASSES


def migrate(apply_changes=False):
    total_changed = 0
    for cls_id in ALL_CLASSES:
        obj, sha = _load_class_file(cls_id)
        if not obj:
            print(f"  {cls_id}: could not load, skipping")
            continue

        changed = []
        for p in obj.get('pupils', []):
            if 'adapted_hl' not in p:
                continue
            was_adapted = bool(p.get('adapted_hl'))
            p['maths_level']   = 'adapted' if was_adapted else 'standard'
            p['reading_level'] = 'phonics' if was_adapted else 'standard'
            del p['adapted_hl']
            changed.append(f"{p.get('first','?')} {p.get('last','')} "
                            f"(was adapted_hl={was_adapted} -> "
                            f"maths={p['maths_level']}, reading={p['reading_level']})")

        if not changed:
            print(f"  {cls_id}: nothing to migrate")
            continue

        print(f"  {cls_id}: {len(changed)} pupil(s)")
        for line in changed:
            print(f"    - {line}")
        total_changed += len(changed)

        if apply_changes:
            ok = _save_class_file(cls_id, obj, sha, 'Migrate adapted_hl to maths_level/reading_level')
            print(f"    saved: {ok}")

    print(f"\n{'Applied' if apply_changes else 'Would apply'} changes to {total_changed} pupil(s) total.")


if __name__ == '__main__':
    migrate(apply_changes='--apply' in sys.argv)

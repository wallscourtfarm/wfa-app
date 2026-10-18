"""With NO setting at all, a printout without a names file shows INITIALS, never the stored 3-letter stub (18.10.26).
Run: python3 tests/test_print_names_default.py   Fake data only."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop('PRINT_NAMES_FROM_FILE_ONLY', None)
import print_names

STORED = [
    {'id': 'p01', 'pupil_id': 'p_aaaaaaaaaa', 'first': 'Inn', 'last': 'McL', 'cls': 'IM'},
    {'id': 'p02', 'pupil_id': 'p_bbbbbbbbbb', 'first': 'Ann', 'last': 'Lee', 'cls': 'IM'},
    {'id': 'p03', 'pupil_id': 'p_cccccccccc', 'first': 'Ann', 'last': 'Lea', 'cls': 'IM'},    # clashes with p02 on AL
]
assert print_names.file_only() is True
out = print_names.display_pupils(STORED, None)
labels = [p['first'] for p in out]
assert labels[0] == 'IM' and all(p['last'] == '' for p in out), labels
assert len(set(labels)) == 3 and labels[1] != labels[2], labels            # clashing initials get longer labels
assert 'Inn' not in labels and 'McL' not in str(out), 'a stub reached the printout'
# a names file wins for the children it covers; the others stay as initials
named = print_names.display_pupils(STORED, {'p_aaaaaaaaaa': {'first': 'Zebulon', 'last': 'Quillfeather'}})
assert named[0]['first'] == 'Zebulon' and named[0]['last'] == 'Quillfeather' and named[1]['first'] == labels[1]
# the stored objects are untouched
assert STORED[0]['first'] == 'Inn'
# the explicit off switch still exists
os.environ['PRINT_NAMES_FROM_FILE_ONLY'] = '0'
assert print_names.file_only() is False and print_names.display_pupils(STORED, None)[0]['first'] == 'Inn'
print('ALL OK')

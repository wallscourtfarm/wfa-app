"""Run with plain python:  python3 tests/test_print_names.py
Proves that printed sheets take pupils' names from the names supplied with the print request:
  * print_names.parse_names / overlay / display_pupils (validation, copies, env switch),
  * paired lists, recording sheet, TT check, Bee cards POST (and GET), word / rule / homophone
    assessment generate: the PDF text contains the supplied name; with PRINT_NAMES_FROM_FILE_ONLY=1
    and no names it contains the initials instead,
  * the stored (loaded) pupil objects are never mutated,
  * nothing is written anywhere and nothing is logged that contains a supplied name.
Fake pupils and fake names only. No network, no live services."""
import os, sys, io, copy, json, base64, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('GITHUB_TOKEN', 'x')
os.environ.setdefault('ACCESS_GATE', 'off')   # test client has no Cloudflare sign-in
os.environ['PRINT_NAMES_FROM_FILE_ONLY'] = '0'
os.environ.pop('ANTHROPIC_API_KEY', None)

import print_names as pn
from print_names import parse_names, overlay, display_pupils, PrintNamesError

# ── print_names unit tests ───────────────────────────────────────────────────
assert parse_names(None) is None and parse_names({}) is None and parse_names({'names': None}) is None
assert parse_names({'names': {}}) is None
for bad in ([], 'x', 5, [{'a': 1}]):
    try:
        parse_names({'names': bad}); raise SystemExit(f'accepted non-dict {bad!r}')
    except PrintNamesError:
        pass
try:
    parse_names({'names': {f'p{i}': {'first': 'A', 'last': 'B'} for i in range(1001)}}); raise SystemExit('accepted 1001')
except PrintNamesError as e:
    assert 'p1' not in str(e)
assert len(parse_names({'names': {f'p{i}': {'first': 'A', 'last': 'B'} for i in range(1000)}})) == 1000
got = parse_names({'names': {
    'p_a': {'first': 'Ottoline\x00\n\t', 'last': 'Pennywhistle\x07'},       # control chars stripped
    'p_b': {'first': 'X' * 200, 'last': 'Y'},                                # capped at 80
    'p_c': 'not a dict', 'p_d': {'first': 5, 'last': 'ok'}, 'p_e': {}, 'p_f': {'first': '', 'last': ''},
    'p_g': {'first': 'Solo'},                                                # last optional
    '': {'first': 'A', 'last': 'B'}, 7: {'first': 'A'},
}})
assert set(got) == {'p_a', 'p_b', 'p_g'}, got
assert got['p_a'] == {'first': 'Ottoline', 'last': 'Pennywhistle'}, got['p_a']
assert len(got['p_b']['first']) == 80 and got['p_g'] == {'first': 'Solo', 'last': ''}

STORED = [
    {'id': 'p01', 'pupil_id': 'p_aaa', 'first': 'Zebulon', 'last': 'Quillfeather', 'cls': 'IM', 'group': 'main',
     'pair_id': 'p02', 'pair_colour': '#1798d3', 'table': '1', 'tt_set': '2', 'tt_mode': 'x', 'mastered': [], 'word_pos': 0},
    {'id': 'p02', 'pupil_id': 'p_bbb', 'first': 'Zara', 'last': 'Quimby', 'cls': 'IM', 'group': 'main',
     'pair_id': 'p01', 'pair_colour': '#1798d3', 'table': '1', 'tt_set': '2', 'tt_mode': 'x', 'mastered': [], 'word_pos': 0},
    {'id': 'p03', 'pupil_id': 'p_ccc', 'first': 'Wilbur', 'last': 'Fenwick-Dribble', 'cls': 'IM', 'group': 'main',
     'pair_id': '', 'pair_colour': '', 'table': '2', 'tt_set': '2', 'tt_mode': 'x', 'mastered': [], 'word_pos': 0},
]
# Names the "teacher's file" supplies: deliberately DIFFERENT from the stored names so that we can tell them apart.
FILE_NAMES = {'p_aaa': {'first': 'Ottoline', 'last': 'Pennywhistle'},
              'p_bbb': {'first': 'Marigold', 'last': 'Thistlewood'},
              'p_ccc': {'first': 'Barnaby', 'last': 'Cobblestone'}}
FILE_BITS = ['Ottoline', 'Pennywhistle', 'Marigold', 'Thistlewood', 'Barnaby', 'Cobblestone']
STORED_BITS = ['Zebulon', 'Quillfeather', 'Zara', 'Quimby', 'Wilbur', 'Fenwick']

before = copy.deepcopy(STORED)
ov = overlay(STORED, FILE_NAMES)
assert [p['first'] for p in ov] == ['Ottoline', 'Marigold', 'Barnaby'] and ov[0] is not STORED[0]
assert STORED == before, 'overlay mutated its input'
ov2 = overlay(STORED, {'p_bbb': FILE_NAMES['p_bbb']})
assert [p['first'] for p in ov2] == ['Zebulon', 'Marigold', 'Wilbur']
assert [p['first'] for p in overlay(STORED, None)] == ['Zebulon', 'Zara', 'Wilbur']
# env switch off: unmatched keep stored names; on: initials
assert [p['first'] for p in display_pupils(STORED, {'p_bbb': FILE_NAMES['p_bbb']})] == ['Zebulon', 'Marigold', 'Wilbur']
os.environ['PRINT_NAMES_FROM_FILE_ONLY'] = '1'
d = display_pupils(STORED, {'p_bbb': FILE_NAMES['p_bbb']})
assert [(p['first'], p['last']) for p in d] == [('ZeQu', ''), ('Marigold', 'Thistlewood'), ('WF', '')], d
d = display_pupils(STORED, None)
assert [(p['first'], p['last']) for p in d] == [('ZeQu', ''), ('ZaQu', ''), ('WF', '')], d   # same labels as the screens
assert STORED == before, 'display_pupils mutated its input'
os.environ['PRINT_NAMES_FROM_FILE_ONLY'] = '0'
assert [p['first'] for p in display_pupils(STORED, None)] == ['Zebulon', 'Zara', 'Wilbur']
os.environ['PRINT_NAMES_FROM_FILE_ONLY'] = '0'
print('print_names unit tests OK')

# ── Flask app, fully offline ─────────────────────────────────────────────────
import requests, data_manager
import app as appmod
flask_app = appmod.app
flask_app.config['TESTING'] = True
import routes.print_tools as rpt, routes.word_assessment as rwa, routes.rule_assessment as rra
import routes.homophone_assessment as rha, routes.digital_sessions as rds

CLASS = {'class_id': '4IM', 'pupils': copy.deepcopy(STORED)}
CLASS_BEFORE = copy.deepcopy(CLASS)

WRITES = []            # every attempted write, anywhere
def _rec(*a, **k):
    WRITES.append((a, k)); raise AssertionError('a write was attempted during a print request')
for mod in (requests,):
    for fn in ('put', 'post', 'patch', 'delete'):
        setattr(mod, fn, _rec)
for fn in ('_put_file', '_put_file_create', 'save_class', 'save_bee_assessment', 'save_weekly_config',
           'save_custom_rules', 'save_rule_confidence', 'advance_tt_pupils'):
    setattr(data_manager, fn, _rec)
ISSUED = []
rpt.record_issued_words = lambda *a, **k: ISSUED.append((a, k)) or True

for m in (rpt, rwa, rra, rha, rds):
    m.load_class = lambda cid: CLASS
    m._resolve_classes = lambda cls: ['4IM']
    m.get_year_group = lambda cls: '4'
    m.load_weekly_config = lambda yr: {'week_ref': 'T1W1'}
rpt._get_rules = lambda cls, week_ref=None: ((0, 0, 'Focus', ['about', 'above'], 0), None, 'T1W1')
rwa._load_cloze_bank = lambda: {}
rra._load_rule_cloze = lambda: {}
rha._load_rule_cloze = lambda: {}

# capture ALL log output
LOG = io.StringIO()
h = logging.StreamHandler(LOG)
logging.getLogger().addHandler(h); logging.getLogger().setLevel(logging.DEBUG)
flask_app.logger.addHandler(h); flask_app.logger.setLevel(logging.DEBUG)

import fitz
def pdf_text(b):
    doc = fitz.open(stream=b, filetype='pdf')
    t = '\n'.join(pg.get_text() for pg in doc)
    doc.close()
    return t

def has_all(t, bits): return all(b in t for b in bits)
def has_none(t, bits): return not any(b in t for b in bits)

def b64pdf(d, key):
    assert d.get('ok'), d
    return base64.b64decode(d[key])

def check(label, make):
    """make(names_or_None) -> pdf bytes. Checks the four cases."""
    # 1. names supplied -> file names on the sheet, stored names not
    os.environ['PRINT_NAMES_FROM_FILE_ONLY'] = '0'
    t = pdf_text(make(FILE_NAMES))
    assert has_all(t, ['Ottoline', 'Marigold', 'Barnaby']), f'{label}: supplied first names missing\n{t[:400]}'
    assert has_none(t, STORED_BITS), f'{label}: a stored name leaked despite names supplied'
    # 2. none supplied, switch off -> stored names (today's behaviour)
    t = pdf_text(make(None))
    assert has_all(t, ['Zebulon', 'Zara', 'Wilbur']), f'{label}: stored names missing with no names'
    # 3. none supplied, switch on -> initials, no names at all
    os.environ['PRINT_NAMES_FROM_FILE_ONLY'] = '1'
    t = pdf_text(make(None))
    assert has_none(t, STORED_BITS + FILE_BITS), f'{label}: a name printed with switch on and none supplied'
    assert 'ZeQu' in t and 'ZaQu' in t and 'WF' in t, f'{label}: initials missing\n{t[:400]}'
    # 4. switch on and names supplied -> supplied names win
    t = pdf_text(make(FILE_NAMES))
    assert has_all(t, ['Ottoline', 'Barnaby']) and has_none(t, STORED_BITS)
    os.environ['PRINT_NAMES_FROM_FILE_ONLY'] = '0'
    print(f'{label}: OK (names from file / stored / initials-with-switch)')

c = flask_app.test_client()
with c.session_transaction() as s:
    s['year_group'] = '4'; s['authed'] = True

def post_json(url, body):
    r = c.post(url, json=body)
    return r

# (paired lists, recording sheet, TT check, Bee cards and Home Learning no longer take names: see tests/test_name_stamps.py)

SESSION = None

# Assessment generate routes
# The word-assessment PUPIL SHEET is name-free (initials + pupil_id code; see tests/test_word_scan.py),
# so names supplied or stored must never appear on it. Only the Excel marking sheet uses the names file.
for _names in (None, FILE_NAMES):
    for _env in (None, '1'):
        os.environ['PRINT_NAMES_FROM_FILE_ONLY'] = '0'
        if _env: os.environ['PRINT_NAMES_FROM_FILE_ONLY'] = _env
        _t = pdf_text(b64pdf(post_json('/api/word-assessment/generate', {'cls': '4IM', 'sections': ['Y3'], **({'names': _names} if _names else {})}).get_json(), 'pdf'))
        assert has_none(_t, STORED_BITS + FILE_BITS), 'word-assessment sheet carries a name'
os.environ['PRINT_NAMES_FROM_FILE_ONLY'] = '0'
print('word-assessment/generate: pupil sheet has no names')
# (the marking spreadsheet now carries initials too: see tests/test_name_stamps.py)

# rule + homophone generate: fake cloze banks, real section builders and PDF builders
RULE_CLOZE = {'y5-t1-w1-l1': {'title': 'Rule one', 'sentences': [
    {'word': 'about', 'sentence': 'I know ____ it.'}, {'word': 'above', 'sentence': 'It is ____ me.'}]}}
rra._load_rule_cloze = lambda: RULE_CLOZE
# Rule + homophone PUPIL SHEETS are name-free too (initials + pupil_id code; see tests/test_rule_scan.py and
# tests/test_homophone_scan.py): names supplied or stored must never appear, and supplied names are ignored.
def _no_names_sheet(label, path, body):
    for _names in (None, FILE_NAMES):
        for _env in (None, '1'):
            os.environ['PRINT_NAMES_FROM_FILE_ONLY'] = '0'
            if _env: os.environ['PRINT_NAMES_FROM_FILE_ONLY'] = _env
            _t = pdf_text(b64pdf(post_json(path, {**body, **({'names': _names} if _names else {})}).get_json(), 'pdf'))
            assert has_none(_t, STORED_BITS + FILE_BITS), f'{label} sheet carries a name'
    os.environ['PRINT_NAMES_FROM_FILE_ONLY'] = '0'
    print(f'{label}/generate: pupil sheet has no names')
_no_names_sheet('rule-assessment', '/api/rule-assessment/generate', {'cls': '4IM', 'rules': ['y5-t1-w1-l1']})
rha._load_rule_cloze = lambda: {}
_no_names_sheet('homophone-assessment', '/api/homophone-assessment/generate', {'cls': '4IM', 'stages': [1, 2, 3]})

# Session creation copies pupil_id (additive) so cards can be matched to a names file later
SAVED = []
rds._save_session = lambda sid, data: SAVED.append(copy.deepcopy(data)) or True
rds._week_snapshot = lambda wc, ref: wc
rds._rule_words = lambda wc, cls: ['above']
r = c.post('/api/live/bee/create', json={'cls': '4IM'}).get_json()
assert r['ok'], r
assert [p['pupil_id'] for p in SAVED[-1]['pupils']] == ['p_aaa', 'p_bbb', 'p_ccc']
rds._save_session = lambda sid, data: SAVED.append(copy.deepcopy(data)) or True
rds._load_cloze_bank = lambda: {}
r = c.post('/api/live/assess/create', json={'type': 'word', 'cls': '4IM', 'sections': ['Y3']}).get_json()
assert r['ok'], r
assert {p['pupil_id'] for p in SAVED[-1]['pupils']} == {'p_aaa', 'p_bbb', 'p_ccc'}
print('bee/assess create: pupil_id copied into session pupils')

# ── nothing written, nothing logged, nothing mutated ─────────────────────────
assert not WRITES, f'writes attempted: {len(WRITES)}'
blob = json.dumps(ISSUED, default=str)
assert has_none(blob, FILE_BITS), 'record_issued_words received a supplied name'
logtxt = LOG.getvalue()
assert has_none(logtxt, FILE_BITS), 'a supplied name appeared in the logs'
assert CLASS == CLASS_BEFORE, 'loaded class data was mutated'
print('no writes attempted, record_issued_words got ids/words only, nothing logged, stored objects unchanged')
print('ALL OK')

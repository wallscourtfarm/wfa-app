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
os.environ.pop('PRINT_NAMES_FROM_FILE_ONLY', None)
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
os.environ.pop('PRINT_NAMES_FROM_FILE_ONLY')
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
    os.environ.pop('PRINT_NAMES_FROM_FILE_ONLY', None)
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
    os.environ.pop('PRINT_NAMES_FROM_FILE_ONLY', None)
    print(f'{label}: OK (names from file / stored / initials-with-switch)')

c = flask_app.test_client()
with c.session_transaction() as s:
    s['year_group'] = '4'; s['authed'] = True

def post_json(url, body):
    r = c.post(url, json=body)
    return r

# paired lists (both layouts), recording sheet, TT check
for order in ('partner_pairs', 'double_sided'):
    check(f'paired-lists/{order}', lambda names, order=order: b64pdf(
        post_json('/api/print/paired-lists', {'cls': '4IM', 'print_order': order, **({'names': names} if names else {})}).get_json(), 'data'))
# The recording sheet draws blank cards (build_recording_sheet is called with pupil=None for every card):
# it prints no pupil names at all, so names supplied must not appear either.
for names in (None, FILE_NAMES):
    t = pdf_text(b64pdf(post_json('/api/print/recording-sheet', {'cls': '4IM', **({'names': names} if names else {})}).get_json(), 'data'))
    assert has_none(t, STORED_BITS + FILE_BITS), 'recording sheet unexpectedly carries a name'
print('recording-sheet: prints no names (blank cards), supplied names are not stored or printed')
check('tt-check', lambda names: b64pdf(
    post_json('/api/print/tt-check', {'cls': '4IM', **({'names': names} if names else {})}).get_json(), 'data'))

# Bee cards: session file stores names + (new) pupil_id; GET still works; POST with names
SESSION = {'session_id': 'ABCD1234', 'week_ref': 'T1W1', 'type': 'spelling_bee', 'items': [], 'pupils': [
    {'id': p['id'], 'pupil_id': p['pupil_id'], 'first': p['first'], 'last': p['last'], 'cls': 'IM',
     'pair_colour': '#1798d3', 'items': [{'word': 'about'}, {'word': 'above'}],
     'partner_id': p['pair_id'], 'partner_name': next((q['first'] for q in STORED if q['id'] == p['pair_id']), '')}
    for p in STORED]}
SESSION_BEFORE = copy.deepcopy(SESSION)
rds._load_session = lambda sid: SESSION if sid == 'ABCD1234' else None
def cards(names):
    if names is None:
        r = c.get('/api/live/bee/cards-pdf/ABCD1234')
    else:
        r = c.post('/api/live/bee/cards-pdf/ABCD1234', json={'names': names})
    assert r.status_code == 200 and r.mimetype == 'application/pdf', (r.status_code, r.get_data()[:200])
    return r.get_data()
check('bee cards (GET / POST)', cards)
t = pdf_text(cards(FILE_NAMES))
assert 'Partner: Marigold' in t or ('Partner' in t and 'Marigold' in t), 'partner name not taken from file'
r = c.post('/api/live/bee/cards-pdf/ABCD1234', json={'names': 'nope'})
assert r.status_code == 400 and 'nope' not in r.get_data(as_text=True)
r = c.post('/api/live/bee/cards-pdf/ABCD1234', data='not json', content_type='application/json')
assert r.status_code == 200          # unparseable body = no names, still prints
assert SESSION == SESSION_BEFORE, 'bee session object was mutated'
# old session without pupil_id: names cannot match -> stored names (switch off) / initials (switch on)
OLD = copy.deepcopy(SESSION)
for p in OLD['pupils']: p.pop('pupil_id')
rds._load_session = lambda sid: OLD
t = pdf_text(cards(FILE_NAMES))
assert has_all(t, ['Zebulon']) and has_none(t, FILE_BITS)
os.environ['PRINT_NAMES_FROM_FILE_ONLY'] = '1'
t = pdf_text(cards(FILE_NAMES)); os.environ.pop('PRINT_NAMES_FROM_FILE_ONLY')
assert has_none(t, STORED_BITS + FILE_BITS)
rds._load_session = lambda sid: SESSION
print('bee cards: old sessions without pupil_id fall back safely')

# Assessment generate routes
check('word-assessment/generate', lambda names: b64pdf(
    post_json('/api/word-assessment/generate', {'cls': '4IM', 'sections': ['Y3'], **({'names': names} if names else {})}).get_json(), 'pdf'))
# the marking spreadsheet is also built from the displayed names
import openpyxl
d = post_json('/api/word-assessment/generate', {'cls': '4IM', 'sections': ['Y3'], 'names': FILE_NAMES}).get_json()
wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(d['excel'])))
cells = ' '.join(str(cell.value) for ws in wb for row in ws.iter_rows() for cell in row if cell.value)
assert has_all(cells, ['Ottoline', 'Marigold']) and has_none(cells, STORED_BITS), 'excel names'
print('word-assessment Excel: names from file')

# rule + homophone generate: fake cloze banks, real section builders and PDF builders
RULE_CLOZE = {'y5-t1-w1-l1': {'title': 'Rule one', 'sentences': [
    {'word': 'about', 'sentence': 'I know ____ it.'}, {'word': 'above', 'sentence': 'It is ____ me.'}]}}
rra._load_rule_cloze = lambda: RULE_CLOZE
check('rule-assessment/generate', lambda names: b64pdf(
    post_json('/api/rule-assessment/generate', {'cls': '4IM', 'rules': ['y5-t1-w1-l1'], **({'names': names} if names else {})}).get_json(), 'pdf'))
rha._load_rule_cloze = lambda: {}
check('homophone-assessment/generate', lambda names: b64pdf(
    post_json('/api/homophone-assessment/generate', {'cls': '4IM', 'stages': [1, 2, 3], **({'names': names} if names else {})}).get_json(), 'pdf'))
r = post_json('/api/word-assessment/generate', {'cls': '4IM', 'sections': ['Y3'], 'names': ['x']})
assert r.status_code == 400 and r.get_json()['ok'] is False
r = post_json('/api/print/paired-lists', {'cls': '4IM', 'names': 'oops'})
assert r.status_code == 400 and 'oops' not in r.get_data(as_text=True)

# Home learning (async job): with names, the finished PDFs live in process memory only, never in /tmp/hl_jobs
import time, routes.home_learning as rhl, hl_generator
rhl.load_class = lambda cid: CLASS
rhl.load_weekly_config = lambda yr: {'week_ref': 'T1W1', 'selected_words': ['about', 'above']}
rhl.get_year_group = lambda cls: '4'
hl_generator.generate_hl_content = lambda **k: {'questions': [], 'grid_elements': [], 'grid_size': 10}
def hl(names):
    body = {'cls': '4IM', 'maths_topic': 'Fractions', 'reading_topic': 'A story'}
    if names: body['names'] = names
    r = c.post('/api/hl/generate', json=body).get_json()
    assert r['ok'], r
    for _ in range(100):
        st = c.get('/api/hl/status/' + r['job_id']).get_json()
        if st.get('status') in ('done', 'error'): break
        time.sleep(0.1)
    assert st['status'] == 'done', st
    disk = rhl._job_read(r['job_id'])
    return st, disk
st, disk = hl(FILE_NAMES)
t = pdf_text(base64.b64decode(st['std_pdf']))
assert has_all(t, ['Ottoline', 'Marigold', 'Barnaby']) and has_none(t, STORED_BITS), 'HL names'
assert 'std_pdf' not in disk and disk.get('status') == 'pending', 'HL result with names was written to disk'
st, disk = hl(None)
t = pdf_text(base64.b64decode(st['std_pdf']))
assert has_all(t, ['Zebulon']) and 'std_pdf' in disk            # unchanged behaviour without names
os.environ['PRINT_NAMES_FROM_FILE_ONLY'] = '1'
st, disk = hl(None); os.environ.pop('PRINT_NAMES_FROM_FILE_ONLY')
t = pdf_text(base64.b64decode(st['std_pdf']))
assert has_none(t, STORED_BITS + FILE_BITS) and 'ZeQu' in t, 'HL initials'
print('home-learning generate: names from file (memory only), stored names without, initials with switch')

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

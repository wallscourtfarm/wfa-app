"""Run with plain python:  python3 tests/test_name_stamps.py
Printed sheets are drawn with INITIALS; real names are never sent to the server. Every name slot is logged in the PDF's
/Keywords (stamps.py) so the teacher's browser can write the names. Fake pupils/names only."""
import os, sys, io, copy, json, base64, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('GITHUB_TOKEN', 'x')
os.environ.setdefault('ACCESS_GATE', 'off')   # test client has no Cloudflare sign-in
os.environ.pop('PRINT_NAMES_FROM_FILE_ONLY', None)
os.environ.pop('ANTHROPIC_API_KEY', None)


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


import fitz, json as _j
from pypdf import PdfReader

def pdf_text(b):
    doc = fitz.open(stream=b, filetype='pdf'); t = '\n'.join(pg.get_text() for pg in doc); doc.close(); return t

def stamps_of(b):
    kw = PdfReader(io.BytesIO(b)).metadata.get('/Keywords')
    assert kw.startswith('WFASTAMPS2:'), kw[:30]
    return _j.loads(kw[11:])

def no_names(t):
    assert not any(x in t for x in STORED_BITS + FILE_BITS), 'a name reached the PDF'

c = flask_app.test_client()
with c.session_transaction() as s:
    s['year_group'] = '4'; s['authed'] = True
def b64(r):
    d = r.get_json(); assert d.get('ok'), d; return base64.b64decode(d['data'])

# names in the request are ignored (never used, never stored)
for order, ids in (('partner_pairs', {'p_aaa', 'p_bbb', 'p_ccc'}), ('double_sided', {'p_aaa', 'p_bbb', 'p_ccc'})):
    pdf = b64(c.post('/api/print/paired-lists', json={'cls': '4IM', 'print_order': order, 'names': FILE_NAMES}))
    no_names(pdf_text(pdf)); st = stamps_of(pdf)
    assert {x['id'] for x in st} == ids and all(x['m'] == 'f' and x.get('pill') for x in st), (order, st)
    assert all('w' in x and x['s'] in (10, 11) for x in st)
print('paired lists: initials only, one pill stamp per child')

pdf = b64(c.post('/api/print/recording-sheet', json={'cls': '4IM', 'names': FILE_NAMES}))
no_names(pdf_text(pdf)); assert isinstance(stamps_of(pdf), list)
pdf = b64(c.post('/api/print/tt-check', json={'cls': '4IM', 'names': FILE_NAMES}))
no_names(pdf_text(pdf)); st = stamps_of(pdf)
assert {x['id'] for x in st} == {'p_aaa', 'p_bbb', 'p_ccc'} and all(x['m'] == 'n' for x in st), st
print('recording sheet / tt check: initials only, stamps present')

SESSION = {'session_id': 'ABCD1234', 'week_ref': 'T1W1', 'type': 'spelling_bee', 'items': [], 'pupils': [
    {'id': p['id'], 'pupil_id': p['pupil_id'], 'first': p['first'], 'last': p['last'], 'cls': 'IM',
     'pair_colour': '#1798d3', 'items': [{'word': 'about'}, {'word': 'above'}],
     'partner_id': p['pair_id'], 'partner_name': next((q['first'] for q in STORED if q['id'] == p['pair_id']), '')}
    for p in STORED]}
rds._load_session = lambda sid: SESSION
for r in (c.get('/api/live/bee/cards-pdf/ABCD1234'), c.post('/api/live/bee/cards-pdf/ABCD1234', json={'names': FILE_NAMES})):
    assert r.status_code == 200 and r.mimetype == 'application/pdf'
    pdf = r.get_data(); no_names(pdf_text(pdf)); st = stamps_of(pdf)
    own = [x for x in st if not x.get('pre')]; part = [x for x in st if x.get('pre') == 'Partner: ']
    assert {x['id'] for x in own} == {'p_aaa', 'p_bbb', 'p_ccc'} and all(x['m'] == 'n' and x['a'] == 'c' for x in own), st
    assert {x['id'] for x in part} == {'p_aaa', 'p_bbb'} and all(x['m'] == 'f' for x in part), part   # partners of p01/p02
print('bee cards: initials only; name + partner stamps (partner by pupil_id); request names ignored')

# word-assessment Excel: initials only; name cells listed in the workbook Keywords
import openpyxl
rwa._load_cloze_bank = lambda: {}
d = c.post('/api/word-assessment/generate', json={'cls': '4IM', 'sections': ['Y3'], 'names': FILE_NAMES}).get_json()
assert d.get('ok'), d
wbk = openpyxl.load_workbook(io.BytesIO(base64.b64decode(d['excel'])))
cells = [str(cell.value) for ws in wbk for row in ws.iter_rows() for cell in row if cell.value]
assert not any(x in ' '.join(cells) for x in STORED_BITS + FILE_BITS), 'a name reached the Excel sheet'
kw = wbk.properties.keywords
assert kw.startswith('WFASTAMPS2X:'), kw
xs = _j.loads(kw[12:])
assert [(x['sh'], x['id']) for x in xs] == [('Marking Grid', 'p_aaa'), ('Marking Grid', 'p_bbb'), ('Marking Grid', 'p_ccc'),
                                          ('Results', 'p_aaa'), ('Results', 'p_bbb'), ('Results', 'p_ccc')], xs
print('word-assessment Excel: initials only, name cells recorded')

r = c.post('/api/hl/generate', json={'cls': '4IM'}); assert r.status_code == 404, r.status_code
assert c.get('/home-learning').status_code == 302
print('old home-learning routes gone; /home-learning still redirects')
assert not WRITES, WRITES
print('ALL OK')

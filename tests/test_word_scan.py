"""Run with plain python:  python3 tests/test_word_scan.py
Proves the WORD assessment scan flow is name-free:
  (a) the real sheet builder prints initials + pupil_id code and NO name (PDF text),
  (b) scan_identity.match_code truth table,
  (c) import-stream with a stubbed Anthropic call: prompt has no name instruction, a stubbed code
      is matched to the right pupil, and the SSE events / JSON to the browser carry no names,
  (d) confirm accepts pupil-id identity (and "<class>|<id>" keys), needs no names,
  (e) no write is ever made with a name that was not already stored.
Fake pupils/names only. No network, no live services."""
import os, sys, io, re, json, copy, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('GITHUB_TOKEN', 'x')
os.environ['ANTHROPIC_API_KEY'] = 'test-key-not-real'

import fitz
import scan_identity as si
import app as appmod
import routes.word_assessment as rwa
from assessment_builder import build_word_assessment_pdf

NAMES = ['Zebulon', 'Quillfeather', 'Zara', 'Quimby', 'Wilbur', 'Fenwick', 'Dribble']
PUPILS = [
    {'id': 'p01', 'pupil_id': 'p_k3m4x2q7ab', 'first': 'Zebulon', 'last': 'Quillfeather', 'mastered': ['about'], 'word_pos': 0},
    {'id': 'p02', 'pupil_id': 'p_abcdef2345', 'first': 'Zara', 'last': 'Quimby', 'mastered': [], 'word_pos': 0},
    {'id': 'p03', 'pupil_id': 'p_zzzzzzzzz7', 'first': 'Wilbur', 'last': 'Fenwick-Dribble', 'mastered': [], 'word_pos': 0},
    {'id': 'p04', 'first': 'Olive', 'last': 'Nobody', 'mastered': [], 'word_pos': 0},   # no pupil_id (old data)
]
NAMES += ['Olive', 'Nobody']
CODES = [p.get('pupil_id') for p in PUPILS]
for pid in CODES[:3]:
    assert re.fullmatch(r'p_[a-z2-7]{10}', pid), pid
SECTIONS = [('Commonly misspelled', ['friend', 'people', 'many'])]
STORED_BEFORE = copy.deepcopy(PUPILS)


def text_of(pdf_bytes):
    d = fitz.open(stream=pdf_bytes, filetype='pdf')
    pages = [pg.get_text() for pg in d]
    d.close()
    return pages


def no_names(text, where):
    for n in NAMES:
        assert n.lower() not in text.lower(), f'{where}: leaked {n!r}'


def walk_strings(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from walk_strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from walk_strings(v)
    else:
        yield str(o)


# ── (a) sheet text ────────────────────────────────────────────────────────────
pdf = build_word_assessment_pdf(PUPILS, SECTIONS, {}, 'T1W1')
pages = text_of(pdf)
assert len(pages) == 4, len(pages)
labels = si.labels_for(PUPILS)
for pg, pupil, lab in zip(pages, PUPILS, labels):
    no_names(pg, 'sheet')
    assert lab in pg, (lab, pg)
    if pupil.get('pupil_id'):
        assert f"Code: {pupil['pupil_id']}" in pg
    else:
        assert 'No code' in pg and 'Code: p_' not in pg
    assert 'Name' not in pg and 'name' not in pg, 'a Name field is on the sheet'
print('(a) sheet header: initials + code, no names OK', labels)

# ── (b) match_code truth table ───────────────────────────────────────────────
EXP = [c for c in CODES if c]
A = EXP[0]
assert si.match_code(A, EXP) == (A, 'matched')
assert si.match_code('  P_' + A[2:].upper() + ' ', EXP) == (A, 'matched')                 # case / spaces
assert si.match_code('Code: ' + A, EXP) == (A, 'matched')                                  # label echoed
assert si.match_code(' '.join(A), EXP) == (A, 'matched')                                   # spaced out
assert si.match_code('p_' + A[2:5] + '​' + A[5:], EXP) == (A, 'matched')              # zero-width
assert si.match_code('`' + A + '.`', EXP) == (A, 'matched')                                # punctuation
assert si.match_code(A[:6] + 'q' + A[7:], EXP) == (A, 'fuzzy')                             # one wrong char
assert si.match_code(A[:-1], EXP) == (A, 'fuzzy')                                          # one dropped
assert si.match_code(A + 'x', EXP) == (A, 'fuzzy')                                         # one extra
assert si.match_code('p_abcdef2345'.replace('b', '8'), EXP) == ('p_abcdef2345', 'matched')  # 8 -> b
# digit mapping only helps when it yields a candidate: 1 -> l
assert si.match_code('p_1111111111', ['p_llllllllll']) == ('p_llllllllll', 'matched')
assert si.match_code('p_0000000000', ['p_oooooooooo']) == ('p_oooooooooo', 'matched')
assert si.match_code('p_9999999999', ['p_gggggggggg']) == ('p_gggggggggg', 'matched')
# ambiguous: distance 1 from two expected ids
assert si.match_code('p_aaaaaaaaac', ['p_aaaaaaaaaa', 'p_aaaaaaaaab']) == (None, 'unmatched')
# exact wins even when another id is one away
assert si.match_code('p_aaaaaaaaaa', ['p_aaaaaaaaaa', 'p_aaaaaaaaab']) == ('p_aaaaaaaaaa', 'matched')
# wrong prefix / none / junk
assert si.match_code('q_' + A[2:], EXP) == (None, 'unmatched')
assert si.match_code(A[2:], EXP) == (None, 'unmatched')
assert si.match_code('', EXP) == (None, 'unmatched')
assert si.match_code(None, EXP) == (None, 'unmatched')
assert si.match_code('hello there', EXP) == (None, 'unmatched')
assert si.match_code('p_qqqqqqqqqq', EXP) == (None, 'unmatched')                           # unknown pupil
assert si.match_code(A, []) == (None, 'unmatched')
assert si.match_code('p_', EXP) == (None, 'unmatched')
print('(b) match_code truth table OK')

# ── Flask harness (offline) ──────────────────────────────────────────────────
flask_app = appmod.app
flask_app.config['TESTING'] = True
CLASS = {'class_id': '5IM', 'pupils': copy.deepcopy(PUPILS)}
rwa.load_class = lambda cid: CLASS
rwa._resolve_classes = lambda cls: ['5IM']
rwa.get_year_group = lambda cls: '5'
rwa.load_weekly_config = lambda yr: {'week_ref': 'T1W1'}
rwa._load_cloze_bank = lambda: {}
rwa._sections_from_keys = lambda sel: SECTIONS
c = flask_app.test_client()
with c.session_transaction() as s:
    s['year_group'] = '5'; s['authed'] = True

# generate route: sheet has no names even when a names file is supplied; excel may use the file
FILE_NAMES = {p['pupil_id']: {'first': 'Ottoline', 'last': 'Pennywhistle'} for p in PUPILS if p.get('pupil_id')}
r = c.post('/api/word-assessment/generate', json={'cls': '5IM', 'sections': ['Y1/Y2'], 'names': FILE_NAMES})
d = r.get_json(); assert d['ok'], d
gen_text = '\n'.join(text_of(base64.b64decode(d['pdf'])))
no_names(gen_text, 'generate pdf'); assert 'Ottoline' not in gen_text and 'Pennywhistle' not in gen_text
assert d['n_no_code'] == 1
for k in ('teacher_pdf',):
    t = '\n'.join(text_of(base64.b64decode(d[k]))); no_names(t, k); assert 'Ottoline' not in t
print('generate route: pdf has no names even with a names file OK')

# ── (c) import-stream with stubbed Anthropic ─────────────────────────────────
SENT = []          # (prompt, image_b64) as sent to "Anthropic"
REPLIES = {}       # call index -> text

class FakeResp:
    def __init__(self, text, code=200): self.status_code = code; self._t = text
    def json(self): return {'content': [{'text': self._t}]}

def fake_post(url, headers=None, json=None, timeout=None, **kw):
    assert url == rwa.ANTHROPIC_URL, url
    content = json['messages'][0]['content']
    img = next(x for x in content if x['type'] == 'image')['source']['data']
    prompt = next(x for x in content if x['type'] == 'text')['text']
    SENT.append((prompt, img))
    i = len(SENT) - 1
    return FakeResp(REPLIES[i])

rwa._req.post = fake_post       # no real network in this process

# pages: p1 exact, p2 one-char error (fuzzy), p3 garbled -> unmatched, p4 no-code pupil -> unmatched
tick = '{"results": {"friend": true, "people": false, "many": true}'
REPLIES.update({
    0: '{"code": "%s", %s}' % (PUPILS[0]['pupil_id'], tick[1:]),
    1: '```json\n{"code": "P_%s", %s}\n```' % (PUPILS[1]['pupil_id'][2:5].upper() + 'x' + PUPILS[1]['pupil_id'][6:], tick[1:]),
    2: '{"code": "p_garble", %s}' % tick[1:],
    3: '{"code": "", "name": "Olive Nobody", %s}' % tick[1:],     # a model that volunteers a name anyway
})
# page 2 of the above must be a 1-edit variant: rebuild precisely
REPLIES[1] = '{"code": "%s", %s}' % (PUPILS[1]['pupil_id'][:4] + 'q' + PUPILS[1]['pupil_id'][5:], tick[1:])

up = c.post('/api/word-assessment/import-upload', json={
    'cls': '5IM', 'sections': ['Y1/Y2'], 'pdf': base64.b64encode(pdf).decode(),
    'mark_format': 'circle', 'mark_convention': 'correct'}).get_json()
assert up['ok'] and up['n_pages'] == 4, up
assert all(set(r_) == {'key', 'label', 'has_code'} for r_ in up['roster'])
assert [r_['label'] for r_ in up['roster']] == labels
assert not any(n.lower() in json.dumps(up).lower() for n in NAMES), 'upload response leaked a name'

stream = c.get(f"/api/word-assessment/import-stream/{up['job_id']}")
raw = stream.get_data(as_text=True)
events = [json.loads(l[6:]) for l in raw.splitlines() if l.startswith('data: ')]
pages_ev = [e for e in events if e['type'] == 'page']
assert len(pages_ev) == 4 and events[-1]['type'] == 'done', events

# what was sent out: no name anywhere, code instruction present, images are real PNGs
assert len(SENT) == 4
for prompt, img in SENT:
    assert not re.search(r'\bnames?\b', prompt, re.I), 'prompt mentions name'
    assert 'p_xxxxxxxxxx' in prompt and 'exactly as printed' in prompt
    assert not any(n.lower() in prompt.lower() for n in NAMES)
    assert base64.b64decode(img)[:8] == b'\x89PNG\r\n\x1a\n'
print('(c) prompt has no name instruction; images are PNGs OK')

# what the browser got
ev_by_page = {e['page_num']: e for e in pages_ev}
assert ev_by_page[1]['status'] == 'matched' and ev_by_page[1]['key'] == PUPILS[0]['pupil_id'] and ev_by_page[1]['label'] == labels[0]
assert ev_by_page[2]['status'] == 'fuzzy' and ev_by_page[2]['key'] == PUPILS[1]['pupil_id'] and ev_by_page[2]['label'] == labels[1]
assert ev_by_page[3]['status'] == 'unmatched' and ev_by_page[3]['key'] == '' and ev_by_page[3]['label'] == ''
assert ev_by_page[4]['status'] == 'unmatched'          # no-code pupil: manual
assert ev_by_page[1]['results'] == {'friend': True, 'people': False, 'many': True}
for e in events:
    assert set(e) <= {'type', 'page_num', 'total', 'key', 'label', 'status', 'results', 'message'}, e   # no 'name'
low = raw.lower()
assert not any(n.lower() in low for n in NAMES), 'SSE leaked a name'
for sx in walk_strings(events):
    assert not any(n.lower() in sx.lower() for n in NAMES)
print('(c) SSE events: initials label + status only, no names OK')

# upload with a bad page does not leak the model reply in an error
REPLIES.clear(); SENT.clear()
for i in range(4): REPLIES[i] = 'not json at all Zebulon Quillfeather'
up = c.post('/api/word-assessment/import-upload', json={
    'cls': '5IM', 'sections': ['Y1/Y2'], 'pdf': base64.b64encode(pdf).decode()}).get_json()
raw = c.get(f"/api/word-assessment/import-stream/{up['job_id']}").get_data(as_text=True)
assert 'Zebulon' not in raw and 'error' in raw
print('(c) unparseable replies produce generic errors OK')

# ── (d)/(e) confirm by pupil id; every write inspected ───────────────────────
GITHUB_FILE = {'sha': 'abc123', 'content': base64.b64encode(
    json.dumps({'class_id': '5IM', 'pupils': copy.deepcopy(PUPILS)}).encode()).decode()}
PUTS = []

class GetResp:
    status_code = 200
    def json(self): return GITHUB_FILE

def fake_get(url, **kw): return GetResp()
def fake_put(url, headers=None, json=None, timeout=None, **kw):
    PUTS.append(json)
    return type('R', (), {'status_code': 200})()
rwa._req.get = fake_get
rwa._req.put = fake_put

key_nocode = f"5IM|{PUPILS[3]['id']}"
payload = {'cls': '5IM', 'sections': ['Y1/Y2'], 'results': {
    PUPILS[0]['pupil_id']: {'label': 'ZQ', 'status': 'matched', 'results': {'friend': True, 'people': True, 'many': False}},
    PUPILS[1]['pupil_id']: {'results': {'friend': True}},
    key_nocode: {'results': {'friend': True, 'people': False, 'many': True}},          # manually assigned page
    'p_unknownxxx': {'results': {'friend': True}},                                       # ignored
}}
assert 'name' not in json.dumps(payload).lower().replace('"label"', '')
r = c.post('/api/word-assessment/confirm', json=payload)
d = r.get_json()
assert d['ok'] and d['saved'] == 3, d
assert d['unmatched'] == [labels[2]], d                     # a LABEL, not a stored full name
assert not any(n.lower() in json.dumps(d).lower() for n in NAMES), 'confirm response leaked a name'
print('(d) confirm by pupil id / class|id key OK, unmatched is labels only:', d['unmatched'])

assert len(PUTS) == 1
written = json.loads(base64.b64decode(PUTS[0]['content']))
orig = {'class_id': '5IM', 'pupils': copy.deepcopy(PUPILS)}
by_id = {p['id']: p for p in written['pupils']}
assert by_id['p01']['mastered'] == ['about', 'friend', 'people']
assert by_id['p02']['mastered'] == ['friend']
assert by_id['p04']['mastered'] == ['friend', 'many']
assert by_id['p03']['mastered'] == []
# (e) the only differences from the stored file are mastered / word_pos: no field got a name
for wp, op in zip(written['pupils'], orig['pupils']):
    diff = {k for k in set(wp) | set(op) if wp.get(k) != op.get(k)}
    assert diff <= {'mastered', 'word_pos'}, diff
assert PUTS[0]['message'] == 'Word Assessment import'
# nothing from the request/response chain containing a name was put anywhere new
req_strings = ' '.join(walk_strings(payload)).lower()
assert not any(n.lower() in req_strings for n in NAMES)
print('(e) the only write is the class file, changing mastered/word_pos only OK')

# confirm no longer matches by name: name-keyed payload saves nothing
PUTS.clear()
d = c.post('/api/word-assessment/confirm', json={'cls': '5IM', 'sections': ['Y1/Y2'],
          'results': {'zara quimby': {'name': 'Zara Quimby', 'results': {'friend': True}}}}).get_json()
assert d['ok'] and d['saved'] == 0 and not PUTS
d = c.post('/api/word-assessment/confirm', json={'cls': '5IM', 'results': []})
assert d.status_code == 400
# stored pupils objects in the harness never mutated by generate/stream
assert CLASS['pupils'] == STORED_BEFORE
print('confirm ignores name-keyed input; stored pupils untouched OK')

# ── Optional: legibility of the code strip at 150 DPI ────────────────────────
try:
    d0 = fitz.open(stream=pdf, filetype='pdf')
    pg = d0[0]
    mat = fitz.Matrix(150 / 72, 150 / 72)
    pix = pg.get_pixmap(matrix=mat)
    hit = pg.search_for(f"Code: {PUPILS[0]['pupil_id']}")
    h_px = (hit[0].y1 - hit[0].y0) * 150 / 72 if hit else 0
    w_px = (hit[0].x1 - hit[0].x0) * 150 / 72 if hit else 0
    out = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'word_scan_sheet_p1_150dpi.png')
    pix.save(out)
    print(f'code strip at 150 DPI: text box {w_px:.0f} x {h_px:.0f} px (page {pix.width}x{pix.height}), png: {out}')
except Exception as e:     # renderer missing: skip silently
    pass

print('ALL word-scan tests passed')

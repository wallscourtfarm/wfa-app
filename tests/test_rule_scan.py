"""Run with plain python:  python3 tests/test_rule_scan.py
Proves the RULE assessment scan flow is name-free (mirrors tests/test_word_scan.py):
  (a) the real sheet builder prints initials + pupil_id code and NO name (PDF text),
  (b) import-stream with a stubbed Anthropic call: prompt has no name instruction, a stubbed code
      is matched to the right pupil, and the SSE events / JSON to the browser carry no names,
  (c) confirm accepts pupil-id identity (and "<class>|<id>" keys), needs no names, and still writes
      exactly the same rule_confidence fields,
  (d) no write is ever made with a name that was not already stored.
Fake pupils/names only. No network, no live services."""
import os, sys, io, re, json, copy, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('GITHUB_TOKEN', 'x')
os.environ['ANTHROPIC_API_KEY'] = 'test-key-not-real'

import fitz
import scan_identity as si
import app as appmod
import routes.rule_assessment as rra
from assessment_builder import build_rule_assessment_pdf

NAMES = ['Zebulon', 'Quillfeather', 'Zara', 'Quimby', 'Wilbur', 'Fenwick', 'Dribble', 'Olive', 'Nobody',
         'Ottoline', 'Pennywhistle']
PUPILS = [
    {'id': 'p01', 'pupil_id': 'p_k3m4x2q7ab', 'first': 'Zebulon', 'last': 'Quillfeather', 'rule_confidence': {}},
    {'id': 'p02', 'pupil_id': 'p_abcdef2345', 'first': 'Zara', 'last': 'Quimby'},
    {'id': 'p03', 'pupil_id': 'p_zzzzzzzzz7', 'first': 'Wilbur', 'last': 'Fenwick-Dribble'},
    {'id': 'p04', 'first': 'Olive', 'last': 'Nobody'},   # no pupil_id (old data)
]
CODES = [p.get('pupil_id') for p in PUPILS]
CLOZE = {
    'r-1': {'title': 'Rule one', 'sentences': [{'word': 'about', 'sentence': 'I know ____ it.'},
                                               {'word': 'above', 'sentence': 'It is ____ me.'}]},
    'r-2': {'title': 'Rule two', 'sentences': [{'word': 'early', 'sentence': 'I woke ____.'},
                                               {'word': 'earth', 'sentence': 'The ____ turns.'}]},
}
SECTIONS = rra._rule_sections(['r-1', 'r-2'], CLOZE)
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
pdf = build_rule_assessment_pdf(PUPILS, SECTIONS, 'T1W1')
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
    assert 'Rule Assessment' in pg
print('(a) sheet header: initials + code, no names OK', labels)

# ── Flask harness (offline) ──────────────────────────────────────────────────
flask_app = appmod.app
flask_app.config['TESTING'] = True
CLASS = {'class_id': '5IM', 'pupils': copy.deepcopy(PUPILS)}
rra.load_class = lambda cid: CLASS
rra._resolve_classes = lambda cls: ['5IM']
rra.get_year_group = lambda cls: '5'
rra.load_weekly_config = lambda yr: {'week_ref': 'T1W1'}
rra._load_rule_cloze = lambda: CLOZE
c = flask_app.test_client()
with c.session_transaction() as s:
    s['year_group'] = '5'; s['authed'] = True

# generate route: sheet has no names even when a names file is supplied (it is ignored)
FILE_NAMES = {p['pupil_id']: {'first': 'Ottoline', 'last': 'Pennywhistle'} for p in PUPILS if p.get('pupil_id')}
d = c.post('/api/rule-assessment/generate', json={'cls': '5IM', 'rules': ['r-1', 'r-2'], 'names': FILE_NAMES}).get_json()
assert d['ok'], d
for k in ('pdf', 'teacher_pdf'):
    t = '\n'.join(text_of(base64.b64decode(d[k]))); no_names(t, k)
assert d['n_no_code'] == 1 and d['n_pupils'] == 4
no_names(json.dumps({k: v for k, v in d.items() if k not in ('pdf', 'teacher_pdf')}), 'generate json')
print('generate route: pdf has no names even with a names file OK')

# ── (b) import-stream with stubbed Anthropic ─────────────────────────────────
SENT = []
REPLY_BY_IMG = {}   # page image (b64) -> reply text. Pages are processed in threads, so key by image.

class FakeResp:
    def __init__(self, text, code=200): self.status_code = code; self._t = text
    def json(self): return {'content': [{'text': self._t}]}

def fake_post(url, headers=None, json=None, timeout=None, **kw):
    assert url == rra.ANTHROPIC_URL, url
    content = json['messages'][0]['content']
    img = next(x for x in content if x['type'] == 'image')['source']['data']
    prompt = next(x for x in content if x['type'] == 'text')['text']
    SENT.append((prompt, img))
    return FakeResp(REPLY_BY_IMG[img])

rra._req.post = fake_post       # no real network in this process

def page_imgs(pdf_bytes, dpi):
    d0 = fitz.open(stream=pdf_bytes, filetype='pdf')
    out = [base64.b64encode(pg.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72)).tobytes('png')).decode() for pg in d0]
    d0.close()
    return out

imgs = page_imgs(pdf, 150)
assert len(set(imgs)) == 4
RES = '"results": {"about": true, "above": false, "early": true, "earth": true}'
fuzzy_code = PUPILS[1]['pupil_id'][:4] + 'q' + PUPILS[1]['pupil_id'][5:]
for img, text in zip(imgs, [
    '{"code": "%s", %s}' % (PUPILS[0]['pupil_id'], RES),
    '```json\n{"code": "%s", %s}\n```' % (fuzzy_code, RES),
    '{"code": "p_garble", %s}' % RES,
    '{"code": "", "name": "Olive Nobody", %s}' % RES,        # a model that volunteers a name anyway
]):
    REPLY_BY_IMG[img] = text

up = c.post('/api/rule-assessment/import-upload', json={
    'cls': '5IM', 'rules': ['r-1', 'r-2'], 'pdf': base64.b64encode(pdf).decode()}).get_json()
assert up['ok'] and up['n_pages'] == 4, up
assert all(set(r_) == {'key', 'label', 'has_code'} for r_ in up['roster'])
assert [r_['label'] for r_ in up['roster']] == labels
assert not any(n.lower() in json.dumps(up).lower() for n in NAMES), 'upload response leaked a name'

raw = c.get(f"/api/rule-assessment/import-stream/{up['job_id']}").get_data(as_text=True)
events = [json.loads(l[6:]) for l in raw.splitlines() if l.startswith('data: ')]
pages_ev = [e for e in events if e['type'] == 'page']
assert len(pages_ev) == 4 and events[-1]['type'] == 'done', events

assert len(SENT) == 4
for prompt, img in SENT:
    assert not re.search(r'\bnames?\b', prompt, re.I), 'prompt mentions name'
    assert 'p_xxxxxxxxxx' in prompt and 'exactly as printed' in prompt
    assert not any(n.lower() in prompt.lower() for n in NAMES)
    assert base64.b64decode(img)[:8] == b'\x89PNG\r\n\x1a\n'
print('(b) prompt has no name instruction; images are PNGs OK')

ev_by_page = {e['page_num']: e for e in pages_ev}
assert ev_by_page[1]['status'] == 'matched' and ev_by_page[1]['key'] == PUPILS[0]['pupil_id'] and ev_by_page[1]['label'] == labels[0]
assert ev_by_page[2]['status'] == 'fuzzy' and ev_by_page[2]['key'] == PUPILS[1]['pupil_id'] and ev_by_page[2]['label'] == labels[1]
assert ev_by_page[3]['status'] == 'unmatched' and ev_by_page[3]['key'] == '' and ev_by_page[3]['label'] == ''
assert ev_by_page[4]['status'] == 'unmatched'          # no-code pupil: manual
assert ev_by_page[1]['results'] == {'about': True, 'above': False, 'early': True, 'earth': True}
for e in events:
    assert set(e) <= {'type', 'page_num', 'total', 'key', 'label', 'status', 'results', 'message'}, e   # no 'name'
assert not any(n.lower() in raw.lower() for n in NAMES), 'SSE leaked a name'
for sx in walk_strings(events):
    assert not any(n.lower() in sx.lower() for n in NAMES)
print('(b) SSE events: initials label + status only, no names OK')

# unparseable replies: generic errors, no leak of the model reply
for img in imgs: REPLY_BY_IMG[img] = 'not json at all Zebulon Quillfeather'
up = c.post('/api/rule-assessment/import-upload', json={
    'cls': '5IM', 'rules': ['r-1', 'r-2'], 'pdf': base64.b64encode(pdf).decode()}).get_json()
raw = c.get(f"/api/rule-assessment/import-stream/{up['job_id']}").get_data(as_text=True)
assert 'Zebulon' not in raw and 'error' in raw and 'Could not read this page.' in raw
print('(b) unparseable replies produce generic errors OK')

# ── (c)/(d) confirm by pupil id; every write inspected ───────────────────────
GITHUB_FILE = {'sha': 'abc123', 'content': base64.b64encode(
    json.dumps({'class_id': '5IM', 'pupils': copy.deepcopy(PUPILS)}).encode()).decode()}
PUTS = []

class GetResp:
    status_code = 200
    def json(self): return GITHUB_FILE

def fake_put(url, headers=None, json=None, timeout=None, **kw):
    PUTS.append(json)
    return type('R', (), {'status_code': 200})()
rra._req.get = lambda url, **kw: GetResp()
rra._req.put = fake_put

key_nocode = f"5IM|{PUPILS[3]['id']}"
payload = {'cls': '5IM', 'rules': ['r-1', 'r-2'], 'week_ref': 'T1W1', 'results': {
    PUPILS[0]['pupil_id']: {'label': 'ZQ', 'status': 'matched',
                            'results': {'about': True, 'above': True, 'early': True, 'earth': False}},
    PUPILS[1]['pupil_id']: {'results': {'about': True}},
    key_nocode: {'results': {'about': False, 'above': False, 'early': True, 'earth': True}},   # manual page
    'p_unknownxxx': {'results': {'about': True}},                                                # ignored
}}
assert 'name' not in json.dumps(payload).lower().replace('"label"', '')
d = c.post('/api/rule-assessment/confirm', json=payload).get_json()
assert d['ok'] and d['saved'] == 3, d
assert d['unmatched'] == [labels[2]], d
assert not any(n.lower() in json.dumps(d).lower() for n in NAMES), 'confirm response leaked a name'
print('(c) confirm by pupil id / class|id key OK, unmatched is labels only:', d['unmatched'])

assert len(PUTS) == 1 and PUTS[0]['message'] == 'Rule Assessment import'
written = json.loads(base64.b64decode(PUTS[0]['content']))
by_id = {p['id']: p for p in written['pupils']}
def last(p, rule): return p['rule_confidence'][rule][-1]
a1, a2 = last(by_id['p01'], 'r-1'), last(by_id['p01'], 'r-2')
assert (a1['status'], a1['correct'], a1['total'], a1['score']) == ('full', 2, 2, 1.0)
assert (a2['status'], a2['correct'], a2['total'], a2['score']) == ('partial', 1, 2, 0.5)
assert set(a1) == {'week', 'rule', 'date', 'status', 'correct', 'total', 'score', 'source'}
assert a1['week'] == 'T1W1' and a1['rule'] == 'Rule one' and a1['source'] == 'reassessment'
b1, b2 = last(by_id['p02'], 'r-1'), last(by_id['p02'], 'r-2')
assert (b1['status'], b2['status']) == ('partial', 'none')          # untested words default to False
d4 = by_id['p04']['rule_confidence']
assert d4['r-1'][-1]['status'] == 'none' and d4['r-2'][-1]['status'] == 'full'
assert 'rule_confidence' not in by_id['p03']
# (d) the only differences from the stored file are rule_confidence: no field got a name
for wp, op in zip(written['pupils'], PUPILS):
    diff = {k for k in set(wp) | set(op) if wp.get(k) != op.get(k)}
    assert diff <= {'rule_confidence'}, diff
assert not any(n.lower() in ' '.join(walk_strings(payload)).lower() for n in NAMES)
print('(d) the only write is the class file, changing rule_confidence only OK')

PUTS.clear()
d = c.post('/api/rule-assessment/confirm', json={'cls': '5IM', 'rules': ['r-1'],
          'results': {'zara quimby': {'name': 'Zara Quimby', 'results': {'about': True}}}}).get_json()
assert d['ok'] and d['saved'] == 0 and not PUTS
assert c.post('/api/rule-assessment/confirm', json={'cls': '5IM', 'results': []}).status_code == 400
assert CLASS['pupils'] == STORED_BEFORE
print('confirm ignores name-keyed input; stored pupils untouched OK')
print('ALL rule-scan tests passed')

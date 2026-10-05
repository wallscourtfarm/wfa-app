"""Build phonics_weeks.py from the ULS Phase 5 lesson-plan PDFs (standard,
Mastery and Year 2 spelling plans).

The PDFs are licensed ULS material, so they stay out of this repo. Extract
them first with `pdftotext -layout` (one file per PDF, each page headed
"##### <name>.pdf / page N"), then run:

    python scripts/build_phonics_weeks.py <dir with 5a.txt 5b.txt 5C.txt
                                           "5a M.txt" "5b M.txt" "5c M.txt" "5a spelling.txt">

Each PDF page is one teaching week: Lessons as columns, and Revisit /
Teach / Practise rows. Words are assigned to a lesson by their horizontal
position under the "Lesson" header.
"""
import os
import re
import sys

# (file stem, id prefix, phase name)
TRACKS = [('5a', 'p5a', 'Phase 5a'), ('5b', 'p5b', 'Phase 5b'), ('5C', 'p5c', 'Phase 5c'),
          ('5a M', 'p5am', 'Phase 5a Mastery'), ('5b M', 'p5bm', 'Phase 5b Mastery'),
          ('5c M', 'p5cm', 'Phase 5c Mastery'), ('5a spelling', 'p5ay2', 'Phase 5a Year 2')]

MARKERS = {
    'revisit': re.compile(r'^(Revisit blending to read|Fluent word reading)$'),
    'recall':  re.compile(r'^(Grapheme recall|Teach days of the week)$'),
    'focus':   re.compile(r'^(Focus GPCs|Focus pronunciations|Focus alternatives|Revise using graphemes?)$'),
    'cew':     re.compile(r'^(Teach new CEW \(read\)|Teach and read CEW|Teach new CEW|'
                          r'Revisit and read|Revisit and spell( CEW)?|Revisit & read|'
                          r'(Read|Spell) CEWs?)$'),
    'gpc':     re.compile(r'^(Teach new GPC|Teach new pronunciation|Teach alternative spelling|'
                          r'Teach spelling|Using graphemes?|Rule for spelling)$'),
    'read':    re.compile(r'^Blending for reading$'),
    'spell':   re.compile(r'^(Segment and write for|spelling:?)$'),
}

# "Teach correct use of nk" and "Spell CEW Monday" carry their content on the
# marker line itself: split them into (marker, remainder).
INLINE = [('gpc', re.compile(r'^Teach correct use of (.+)$')),
          ('cew', re.compile(r'^(?:Read|Spell) CEWs? (.+)$'))]

SKIP = re.compile(r'^(Recap |Unlocking Letters|far, |slides|clicking |so far|Practise common|'
                  r'misconceptions|the phase)')

# Word runs too wide for their column, which pdftotext prints as one
# run spanning two lessons. Each maps to the split shown in the PDF.
OVERRIDES = {
    ('5a', 1, 'revisit'): {3: ['about', 'proud', 'mouth'], 4: ['fries', 'untied', 'magpie'],
                           5: ['reach', 'bleat', 'teacher']},
    ('5C', 1, 'revisit'): {3: ['catch', 'fetch', 'kitchen'], 4: ['fudge', 'hedge', 'badger']},
    ('5C', 2, 'read'):    {6: ['gnash', 'design', 'resign'], 7: ['knight', 'knew', 'knead']},
    ('5C', 4, 'revisit'): {18: ['here', 'severe', 'sphere'], 19: ['steer', 'sheer', 'cheering']},
    ('5a M', 1, 'spell'): {1: ['spray', 'Sunday', 'sway'], 2: ['mouth', 'found', 'sprout']},
    ('5b M', 2, 'revisit'): {7: ['robot', "won't", 'going'], 8: ['music', 'stupid', 'human'],
                             9: ['bush', 'awful', 'playful']},
    ('5c M', 1, 'spell'): {3: ['thumb', 'comb', 'climb'], 4: ['knight', 'resign', 'knife']},
    ('5C', 5, 'read'):    {21: ['calm', 'qualm', 'almond'], 22: ['nowhere', 'tear', 'swear']},
}


def _clean_word(w):
    w = w.strip(',.').replace('’', "'").replace('ﬁ', 'fi').replace('ﬂ', 'fl')
    return w


def _parse_page(lines):
    hdr = next(l for l in lines if l.startswith('Lesson '))
    nums = [int(m.group()) for m in re.finditer(r'\d+', hdr)]
    cents = [m.start() + len(m.group()) / 2 for m in re.finditer(r'\d+', hdr)]
    cols = [{'lesson': n, 'gpc': [], 'focus': [], 'cew': [], 'revisit': [], 'read': [], 'spell': []}
            for n in nums]
    state = [None] * len(nums)
    nearest = lambda x: min(range(len(cents)), key=lambda k: abs(cents[k] - x))
    section = None
    for line in lines:
        m = re.match(r'^(Revisit|Teach|Practise|Apply|Revise|Address)\b', line)
        if m:
            section = m.group(1)
            line = ' ' * len(section) + line[len(section):]
        if section not in ('Revisit', 'Teach', 'Practise'):
            continue
        runs = [r for r in re.finditer(r'\S+(?: \S+)*', line) if not SKIP.match(r.group())]
        # Marker labels on one line are always one per column, in order. A wide
        # label can sit nearer its neighbour's heading, so keep them increasing.
        label_col, prev = {}, -1
        for r in runs:
            if any(rx.match(r.group()) for rx in MARKERS.values()):
                c = nearest((r.start() + r.end()) / 2)
                if c <= prev < len(cents) - 1:
                    c = prev + 1
                label_col[r.start()] = prev = c
        for run in runs:
            text = run.group()
            i = label_col.get(run.start(), nearest((run.start() + run.end()) / 2))
            marker = next((k for k, rx in MARKERS.items() if rx.match(text)), None)
            if marker:
                state[i] = marker
                continue
            inline = next(((k, m) for k, rx in INLINE if (m := rx.match(text))), None)
            if inline:
                state[i] = inline[0]
                cols[i][inline[0]].append(inline[1].group(1))
                continue
            if state[i] in ('revisit', 'read', 'spell'):
                # Word lists: place each word under its own column.
                for wm in re.finditer(r'\S+', text):
                    j = nearest(run.start() + (wm.start() + wm.end()) / 2)
                    if state[j] in ('revisit', 'read', 'spell'):
                        cols[j][state[j]].append(_clean_word(wm.group()))
            elif state[i] in ('gpc', 'focus', 'cew'):
                cols[i][state[i]].append(text)
            elif state[i] == 'recall' and text.endswith('day') and section == 'Teach':
                cols[i]['read'].extend(_clean_word(w) for w in text.split())
    return cols


def _short_gpc(text):
    text = re.split(r'\s+Dependent on accent', text)[0]
    return text.replace(' (South of England)', '').strip()


def _dedupe(words, exclude=()):
    out = []
    for w in words:
        if w and w not in out and w not in exclude:
            out.append(w)
    return out


def build(src):
    weeks = []
    for fname, prefix, phase in TRACKS:
        text = open(os.path.join(src, fname + '.txt'), encoding='utf-8').read()
        pages = re.split(r'^##### .*$', text, flags=re.M)[1:]
        for wk, page in enumerate(pages, 1):
            cols = _parse_page(page.split('\n'))
            for (f, w, field), split in OVERRIDES.items():
                if f == fname and w == wk:
                    for c in cols:
                        if c['lesson'] in split:
                            c[field] = list(split[c['lesson']])
            lessons = []
            for c in cols:
                if not (c['spell'] or c['read'] or c['revisit'] or c['cew']):
                    continue    # e.g. a final lesson that only practises misconceptions
                gpc = _short_gpc(' '.join(c['gpc']))
                tricky = _dedupe(w for t in c['cew'] for w in t.split())
                lessons.append({
                    'lesson':   c['lesson'],
                    'focus':    gpc or 'Review: ' + ' '.join(c['focus']).strip() if (gpc or c['focus']) else 'Review',
                    'tricky':   tricky,
                    'spelling': _dedupe(c['spell']),
                    'reading':  _dedupe(c['read']),
                    'revisit':  _dedupe(c['revisit']),
                })
            spelling = _dedupe(w for l in lessons for w in l['spelling'])
            reading = _dedupe((w for l in lessons for w in l['reading']), spelling)
            revisit = _dedupe((w for l in lessons for w in l['revisit']), spelling + reading)
            gpcs = [l['focus'] for l in lessons if not l['focus'].startswith('Review')]
            first, last = cols[0]['lesson'], cols[-1]['lesson']
            weeks.append({
                'id':         f"{prefix}_w{wk}",
                'phase':      phase,
                'week':       wk,
                'label':      f"Week {wk} (Lessons {first}–{last})",
                'gpcs_label': ', '.join(gpcs),
                'lessons':    lessons,
                'spelling':   spelling,
                'reading':    reading,
                'revisit':    revisit,
                'tricky':     _dedupe(w for l in lessons for w in l['tricky']),
            })
    return weeks


def main():
    weeks = build(sys.argv[1])
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'phonics_weeks.py')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write('# Auto-generated by scripts/build_phonics_weeks.py from the ULS Phase 5\n')
        fh.write('# lesson plans — do not edit by hand. One entry per teaching week (5 lessons).\n')
        fh.write('PHONICS_WEEKS = [\n')
        for w in weeks:
            fh.write('    ' + repr(w) + ',\n')
        fh.write(']\n')
    print(f'Wrote {len(weeks)} weeks to {out}')


if __name__ == '__main__':
    main()

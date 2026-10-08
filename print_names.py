"""Names for PRINTED sheets, supplied by the teacher with each print request.

The server stores initials-only screens; real names live in a "names file" on the
teacher's own computer. When a teacher prints a sheet that carries a child's name,
the browser sends {"names": {pupil_id: {"first": ..., "last": ...}}} with that one
request. This module:

  * validates that object (parse_names),
  * returns COPIES of the pupil dicts with first/last replaced (overlay),
  * decides what a route should print (display_pupils).

Hard rules (see tests/test_print_names.py):
  * names are used in memory to draw one PDF and are then dropped;
  * nothing here (or in a route that uses it) stores, caches, logs or commits them;
  * the loaded / stored pupil objects are never mutated and never saved;
  * error messages never contain a supplied value.

Env switch PRINT_NAMES_FROM_FILE_ONLY (default off). When it is '1', a pupil who
has no supplied name prints as their initials label (names_display) instead of the
stored name. When off (today's behaviour), the stored name is used.
"""
import os
import unicodedata

MAX_ENTRIES = 1000
MAX_STR = 80


class PrintNamesError(ValueError):
    """The 'names' payload was unusable. The message is fixed text (never a supplied value)."""


def file_only():
    """True when stored names must NOT be printed (initials instead) unless supplied."""
    return os.environ.get('PRINT_NAMES_FROM_FILE_ONLY', '').strip() == '1'


def _clean(s):
    """Strip control / format characters, collapse whitespace, cap length. Non-str -> None."""
    if not isinstance(s, str):
        return None
    s = ''.join(ch if unicodedata.category(ch)[0] != 'C' else ' ' for ch in s)
    s = ' '.join(s.split())
    return s[:MAX_STR].strip()


def parse_names(body):
    """Return {pupil_id: {'first': str, 'last': str}} from a request body, or None if none supplied.

    body: the parsed JSON object of the request (or None). Raises PrintNamesError if `names`
    is present but is not an object or has more than MAX_ENTRIES entries. Malformed entries
    are silently ignored.
    """
    if not isinstance(body, dict) or 'names' not in body:
        return None
    raw = body.get('names')
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise PrintNamesError('The names list was not in the expected format.')
    if len(raw) > MAX_ENTRIES:
        raise PrintNamesError('Too many names were supplied.')
    out = {}
    for pid, v in raw.items():
        pid = _clean(pid) if isinstance(pid, str) else None
        if not pid or not isinstance(v, dict):
            continue
        first = _clean(v.get('first', ''))
        last = _clean(v.get('last', ''))
        if first is None or last is None or not (first or last):
            continue
        out[pid] = {'first': first, 'last': last}
    return out or None


def overlay(pupils, names):
    """New pupil dicts (shallow copies); first/last replaced where pupil_id is in `names`.
    The input list and its dicts are never modified."""
    names = names or {}
    out = []
    for p in pupils:
        q = dict(p)
        n = names.get(p.get('pupil_id') or '')
        if n:
            q['first'] = n['first']
            q['last'] = n['last']
        out.append(q)
    return out


def display_pupils(pupils, names):
    """What a route should print: copies of `pupils` with
       - the supplied name for pupils found in `names` (matched by pupil_id), and
       - for the others: the stored name, or, with PRINT_NAMES_FROM_FILE_ONLY=1, the
         initials label (same algorithm as the screens, computed over this list).
    Never mutates `pupils`."""
    pupils = list(pupils)
    out = overlay(pupils, names)
    if not file_only():
        return out
    from names_display import label_list
    names = names or {}
    labels = label_list([(p.get('first') or '', p.get('last') or '') for p in pupils])
    for i, (orig, q) in enumerate(zip(pupils, out)):
        if (orig.get('pupil_id') or '') not in names:
            q['first'] = labels[i]
            q['last'] = ''
    return out


def display_session_pupils(session_pupils, names):
    """As display_pupils, for Spelling Bee session pupils, which also carry a partner's first
    name (partner_name) looked up by partner_id inside the same session."""
    shown = display_pupils(session_pupils, names)
    by_id = {p.get('id'): p for p in shown}
    for q, orig in zip(shown, session_pupils):
        partner = by_id.get(orig.get('partner_id'))
        if partner is not None:
            q['partner_name'] = partner.get('first', '')
        elif file_only():
            q['partner_name'] = ''
    return shown

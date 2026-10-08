"""Pupil initials labels for every staff-facing screen (display only).

The browser must never receive a pupil's first or last name. Anything shown to
a person on screen uses these labels instead; nothing here is stored.

Default label: first letter of the first name + first letter of the LAST word
of the surname, upper case ("Innes McLean" -> "IM"). Letters only (spaces,
hyphens and apostrophes are ignored). Pupils whose labels clash within the SAME
list get 2, then 3... letters of each part ("InMc", "InnMcL"); genuinely
identical names get " 2", " 3" in list order. A single-word name gets its first
two letters, Capitalised.

Printing / PDF / assessment-sheet code keeps using the stored names.
"""
import re as _re


def _letters(s):
    return _re.sub(r"[^A-Za-z]", "", s or "")


def _name_parts(name):
    """Full-name string -> (first, last). Single-word names have last == ''."""
    toks = (name or "").split()
    if not toks:
        return "", ""
    first = _letters(toks[0])
    last = _letters(toks[-1]) if len(toks) > 1 else ""
    return first, last


def _pair_parts(first, last):
    f = _letters((first or "").split()[0]) if (first or "").split() else ""
    lw = (last or "").split()
    l = _letters(lw[-1]) if lw else ""
    return f, l


def _labels_from_parts(parts):
    def lab(i, n):
        f, l = parts[i]
        if not l:
            # single-word name: first two letters, Capitalised
            return f[:2].capitalize()
        if n == 1:
            return (f[:1] + l[:1]).upper()
        fp, lp = f[:n], l[:n]
        return fp[:1].upper() + fp[1:] + lp[:1].upper() + lp[1:]

    lv = [1] * len(parts)
    while True:
        labels = [lab(i, lv[i]) for i in range(len(parts))]
        groups = {}
        for i, t in enumerate(labels):
            groups.setdefault(t.lower(), []).append(i)
        changed = False
        for idxs in groups.values():
            if len(idxs) < 2 or len({(parts[i][0].lower(), parts[i][1].lower()) for i in idxs}) < 2:
                continue
            for i in idxs:
                f, l = parts[i]
                if l and lv[i] < max(len(f), len(l)):
                    lv[i] += 1
                    changed = True
        if not changed:
            break
    seen = {}
    out = []
    for t in labels:
        k = t.lower()
        seen[k] = seen.get(k, 0) + 1
        out.append(t if seen[k] == 1 else f"{t} {seen[k]}")
    return out


def label_list(pairs_or_names):
    """List of full-name strings OR (first, last) pairs -> list of labels, same order."""
    parts = []
    for item in pairs_or_names:
        if isinstance(item, (tuple, list)):
            parts.append(_pair_parts(item[0] if len(item) > 0 else "", item[1] if len(item) > 1 else ""))
        else:
            parts.append(_name_parts(item))
    return _labels_from_parts(parts)


def labels_for_pupils(pupils):
    """List of pupil dicts (first, last, id) -> {pupil_id: label}."""
    pupils = list(pupils)
    labels = label_list([(p.get("first") or "", p.get("last") or "") for p in pupils])
    return {p.get("id", ""): labels[i] for i, p in enumerate(pupils)}

from data_manager import latest_rule_confidence_entry
from word_bank import WORD_BANK
from spelling_rules import SPELLING_RULES

# The '/learners' (Pupils) page was removed 2026-09-20 — Dashboard shows
# everything it did (and more), Admin > Manage Pupils covers the rest
# (partner pairing). These helpers stay: routes/dashboard.py still uses them.

STAGE_YEARS = {2: 'Y2', 3: 'Y3', 4: 'Y4', 5: 'Y5'}

def _homophone_words_by_stage():
    """Returns {stage: [word, ...]} for all homophone rules."""
    result = {}
    for r in SPELLING_RULES:
        stage, step, title, words, rtype = r
        if rtype != 0: continue  # skip challenge and revision
        if 'homophone' not in title.lower() and 'near-homophone' not in title.lower(): continue
        result.setdefault(stage, []).extend(words)
    return result

def _enrich(pupils, homophone_words_by_stage):
    """Add display-ready computed fields to each pupil dict."""
    wb = [w[0] for w in WORD_BANK]   # flat word list
    enriched = []
    for p in pupils:
        pos      = p.get('word_pos', 0)
        mastered = set(p.get('mastered', []))
        hm       = set(w.lower() for w in p.get('homophone_mastered', []))

        # Active key spelling words (next 5 from word_pos)
        active_words = [wb[i] for i in range(pos, min(pos + 5, len(wb)))]

        # Homophone stage summaries derived from homophone_mastered
        hm_stages = []
        for stage in sorted(homophone_words_by_stage):
            stage_words = homophone_words_by_stage[stage]
            correct = sum(1 for w in stage_words if w.lower() in hm)
            total   = len(stage_words)
            pct     = round(correct / total * 100) if total else 0
            # Get last assessed date from history
            hist    = p.get('homophone_history', {}).get(str(stage), [])
            last    = hist[-1]['date'] if hist else None
            status  = ('confident' if pct >= 90 else
                       'partial'   if pct >= 60 else
                       'not assessed' if not last else 'developing')
            hm_stages.append({
                'stage': stage,
                'label': f"Stage {stage} ({STAGE_YEARS.get(stage, '')})",
                'correct': correct, 'total': total, 'pct': pct,
                'status': status, 'last_date': last,
            })

        # Rule confidence — latest entry per rule (a full Reassessment always
        # outranks a weekly Bee tick — see latest_rule_confidence_entry)
        rc_latest = []
        for rule_id, entries in sorted(p.get('rule_confidence', {}).items()):
            latest = latest_rule_confidence_entry(entries)
            if not latest: continue
            rc_latest.append({
                'rule_id':  rule_id,
                'title':    latest.get('rule', rule_id),
                'status':   latest.get('status', '—'),
                'correct':  latest.get('correct', '?'),
                'total':    latest.get('total', '?'),
                'week':     latest.get('week', ''),
                'date':     latest.get('date', ''),
            })

        enriched.append({**p,
            'active_words':  active_words,
            'mastered_count': len(mastered),
            'hm_stages':     hm_stages,
            'rc_latest':     rc_latest,
        })
    return enriched

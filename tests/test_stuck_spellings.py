"""Stuck key spellings: words a child has been handed in several different weeks and not mastered."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_manager import stuck_words_for_pupil


def _pupil(issued, mastered=()):
    return {'id': 'p01', 'issued_words': issued, 'mastered': list(mastered)}


def test_counts_distinct_weeks_not_prints():
    p = _pupil({'T1W2': ['said', 'they'], 'T1W3': ['said', 'they'], 'T1W4': ['said', 'were']})
    out = stuck_words_for_pupil(p, 3)
    assert [w['word'] for w in out] == ['said']
    assert out[0]['n'] == 3 and out[0]['weeks'] == ['T1W2', 'T1W3', 'T1W4']


def test_threshold_and_ordering():
    p = _pupil({'T1W2': ['said', 'they'], 'T1W3': ['said', 'they'], 'T1W4': ['said', 'were']})
    out = stuck_words_for_pupil(p, 2)
    assert [w['word'] for w in out] == ['said', 'they']      # most weeks first


def test_mastered_words_drop_off_case_insensitively():
    p = _pupil({'T1W2': ['Said'], 'T1W3': ['Said'], 'T1W4': ['Said']}, mastered=['said'])
    assert stuck_words_for_pupil(p, 3) == []


def test_placeholder_week_never_counted():
    p = _pupil({'TxWy': ['said'], 'T1W5': ['said'], 'T1W6': ['said']})
    assert stuck_words_for_pupil(p, 3) == []
    assert [w['word'] for w in stuck_words_for_pupil(p, 2)] == ['said']


def test_no_history():
    assert stuck_words_for_pupil({'id': 'p01'}, 3) == []
    assert stuck_words_for_pupil({'id': 'p01', 'issued_words': None, 'mastered': None}, 3) == []

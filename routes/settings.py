import os
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import load_weekly_config, save_weekly_config, ALL_CLASSES, get_class_options, load_term_dates, term_dates_by_term, current_week_ref

settings_bp = Blueprint('settings', __name__)
CLASS_OPTIONS = get_class_options(include_all_per_year=False)


def _snapshot_current_uls_week(wc):
    """Snapshot wc's own current ULS fields into wc['weeks'][wc['week_ref']],
    if it has one. Called both before and after applying a save's changes,
    so the OUTGOING week (as it stood before this save) is preserved even
    when this save is switching to a different week — otherwise the first
    time a new week gets set up, the previous week's Bee data would be
    overwritten with no snapshot ever having been taken of it."""
    if wc.get('programme') != 'uls' or not wc.get('week_ref'):
        return
    weeks = wc.setdefault('weeks', {})
    weeks[wc['week_ref']] = {
        'term':           wc.get('term', ''),
        'week':           wc.get('week'),
        'week_ref':       wc.get('week_ref', ''),
        'lesson_ids':     wc.get('lesson_ids', []),
        'hl_mode':        wc.get('hl_mode', ''),
        'hl_lesson_id':   wc.get('hl_lesson_id', ''),
        'selected_words': wc.get('selected_words', []),
        'rule_title':     wc.get('rule_title', ''),
        'year_group':     wc.get('year_group', ''),
        'saved_at':       datetime.now(timezone.utc).isoformat(),
    }


@settings_bp.route('/api/debug/learners')
def api_debug_learners():
    if not session.get('authenticated'):
        return jsonify({'ok': False}), 401
    from data_manager import load_learners
    pupils = load_learners('Y4_all')
    sample = [{'id': p.get('id'), 'first': p.get('first'),
               'pair_id': p.get('pair_id'), 'partner_name': p.get('partner_name')}
              for p in pupils[:3]]
    return jsonify({'ok': True, 'sample': sample})


@settings_bp.route('/api/settings/rule-confidence-summary')
def api_rule_confidence_summary():
    """Dry-run counts for the rule confidence archive/reset tool."""
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    from data_manager import get_rule_confidence_summary
    try:
        return jsonify({'ok': True, 'summary': get_rule_confidence_summary()})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@settings_bp.route('/api/settings/rule-confidence-archive-reset', methods=['POST'])
def api_rule_confidence_archive_reset():
    """Archive every pupil's rule_confidence, then clear it. Does not touch
    mastered/word_pos (CEW/Key Spelling lists)."""
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    from data_manager import archive_and_reset_rule_confidence
    try:
        return jsonify(archive_and_reset_rule_confidence())
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@settings_bp.route('/api/settings/sync-term-dates', methods=['POST'])
def api_sync_term_dates():
    """Pull term dates from the school calendar (WFA database) and save to term_dates.json."""
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401

    # 25.09.26: reads the school calendar from the WFA database (the same TermDates
    # that the School Info Editor edits). This used to read a Google Sheet that
    # nothing updates any more, using a Google service-account key on this server.
    import requests
    from datetime import datetime, timedelta
    try:
        r = requests.get(
            'https://api.wallscourt-farm-academy.co.uk/planning/tab',
            params={'tab': 'TermDates', 'token': '050d7ae1a6b52eafa7d19b80c844dea8d20d1f678274fe05'},
            timeout=30)
        r.raise_for_status()
        payload = r.json()
        if payload.get('error'):
            raise ValueError(payload['error'])
        rows = payload.get('rows') or []
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Could not read the school calendar: {e}'})

    # Expected columns: Term, Week, StartDate (dd/mm/yy)
    # Build term_dates list: [{label, iso, display, term, week}]
    term_dates = []
    for row in rows:
        try:
            term = int(str(row.get('Term', '')).strip())
            week = int(str(row.get('Week', '')).strip())
            raw  = str(row.get('StartDate', '')).strip()
            if not raw:
                continue
            # Try dd/mm/yy then dd/mm/yyyy
            for fmt in ('%d/%m/%y', '%d/%m/%Y'):
                try:
                    dt = datetime.strptime(raw, fmt)
                    break
                except ValueError:
                    continue
            else:
                continue
            iso     = dt.strftime('%Y-%m-%d')
            display = dt.strftime('%-d %b')        # e.g. "1 Sep"
            label   = f'T{term}W{week}'
            term_dates.append({'label': label, 'iso': iso, 'display': display,
                               'term': term, 'week': week})
        except (ValueError, TypeError):
            continue

    if not term_dates:
        return jsonify({'ok': False, 'error': 'No valid rows found in the school calendar'})

    term_dates.sort(key=lambda w: w['iso'])

    from data_manager import _get_file, _put_file, _put_file_create
    path = 'data/term_dates.json'
    _, sha = _get_file(path)
    if sha is None:
        ok = _put_file_create(path, term_dates, 'Sync term dates from the school calendar')
    else:
        ok = _put_file(path, term_dates, sha, 'Sync term dates from the school calendar')

    if ok:
        return jsonify({'ok': True, 'count': len(term_dates),
                        'sample': [w['label'] for w in term_dates[:6]]})
    return jsonify({'ok': False, 'error': 'GitHub write failed'})


@settings_bp.route('/api/settings/uls-weeks')
def api_uls_weeks():
    if not session.get('authenticated'):
        return jsonify({'ok': False}), 401
    year_group = request.args.get('year', 'Y4')
    from data_manager import list_uls_weeks
    from uls_lessons import get_week_lessons, TERM_LABELS
    import re
    weeks = list_uls_weeks(year_group)
    # For each week, return the lesson focuses too
    result = []
    for code, label in weeks:
        m = re.match(r'(T\d)W(\d+)', code)
        if m:
            lessons = get_week_lessons(year_group, m.group(1), int(m.group(2)))
            result.append({
                'code':    code,
                'label':   label,
                'focuses': [l['focus'] for l in lessons],
                'lessonIds': [l['id'] for l in lessons],
            })
    return jsonify({'ok': True, 'weeks': result})


@settings_bp.route('/api/settings/uls-lesson')
def api_uls_lesson():
    if not session.get('authenticated'):
        return jsonify({'ok': False}), 401
    lid = request.args.get('id', '')
    from uls_lessons import get_lesson
    l = get_lesson(lid)
    if not l:
        return jsonify({'ok': False, 'error': 'Not found'})
    return jsonify({'ok': True, 'lesson': l})


@settings_bp.route('/settings')
def settings():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))
    import json
    from data_manager import YEAR_GROUP_CLASSES, get_class_options_for_year
    from phonics_bank import phonics_sets_for_ui
    yr         = session.get('year_group', '4')
    yr_classes = YEAR_GROUP_CLASSES.get(yr, [])
    wc         = load_weekly_config(yr)
    td         = load_term_dates()
    term_dates = term_dates_by_term(td)
    this_week  = current_week_ref(td)
    default_programme = 'phonics' if yr in ('1', '2') else 'uls'
    programme  = wc.get('programme') or default_programme
    return render_template('settings.html',
        wc=wc, yr_classes=yr_classes, active_year=yr,
        class_options=get_class_options_for_year(yr, include_all=False),
        term_dates=term_dates,
        this_week=this_week,
        programme=programme,
        phonics_sets_json=json.dumps(phonics_sets_for_ui()))


@settings_bp.route('/api/settings/save', methods=['POST'])
def api_settings_save():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    body = request.get_json(force=True)

    yr = session.get('year_group', '4')
    wc = load_weekly_config(yr)

    # Preserve whatever week was live coming into this save, before any of
    # its fields get overwritten below — see _snapshot_current_uls_week.
    _snapshot_current_uls_week(wc)

    year_group = body.get('year_group', '').strip()
    if year_group:
        wc['year_group'] = year_group

    programme = body.get('programme', '').strip()
    week      = body.get('week')

    if programme == 'phonics':
        from phonics_bank import get_phonics_set
        set_id = body.get('phonics_set_id', '').strip()
        pset   = get_phonics_set(set_id) if set_id else None
        if pset:
            wc['programme']       = 'phonics'
            wc['phonics_set_id']  = set_id
            wc['selected_words']  = pset['words']
            wc['rule_title']      = f"{pset['phase']}, {pset['label']} ({pset['gpcs_label']})"
            # Clear stale Unlocking Spelling fields so their fallbacks can't
            # leak a previous week's lesson title/words into a phonics week.
            wc['hl_lesson_id'] = ''
            wc['lesson_ids']   = []

    elif programme == 'uls':
        term        = body.get('term', '').strip()
        lesson_ids  = body.get('lesson_ids', [])
        hl_mode     = body.get('hl_mode', 'single')
        hl_lesson_id = body.get('hl_lesson_id', '')
        selected_words = body.get('selected_words', [])

        wc['programme'] = 'uls'
        if term:
            wc['term'] = term
        if week is not None:
            wc['week'] = int(week)
            wc['week_ref'] = f'{term}W{week}'
        if lesson_ids:
            wc['lesson_ids'] = lesson_ids
        if hl_mode:
            wc['hl_mode'] = hl_mode
        if hl_lesson_id:
            wc['hl_lesson_id'] = hl_lesson_id
        if selected_words:
            wc['selected_words'] = selected_words

        # Derive and save rule_title so Streamlit can display it without uls_lessons.py
        from data_manager import get_uls_lesson
        rule_title = ''
        if hl_lesson_id:
            lesson = get_uls_lesson(hl_lesson_id)
            if lesson:
                rule_title = lesson.get('focus', '')
        if not rule_title and lesson_ids:
            lesson = get_uls_lesson(lesson_ids[0])
            if lesson:
                rule_title = lesson.get('focus', '')
        if rule_title:
            wc['rule_title'] = rule_title

        # Clear stale phonics selection now that this week is Unlocking Spelling.
        wc['phonics_set_id'] = ''

    # Legacy week_ref override (shared across both programmes)
    week_ref = body.get('week_ref', '').strip()
    if week_ref and not week:
        wc['week_ref'] = week_ref

    # Snapshot this save's resulting week too (covers a same-week re-save,
    # e.g. tweaking this week's word selection), so the Bee always has an
    # up-to-date snapshot for whichever week Settings currently has live.
    _snapshot_current_uls_week(wc)

    ok = save_weekly_config(yr, wc)
    return jsonify({'ok': ok, 'error': None if ok else 'GitHub write failed'})

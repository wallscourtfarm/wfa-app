import os
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import load_weekly_config, save_weekly_config, ALL_CLASSES, get_class_options, load_term_dates, term_dates_by_term, current_week_ref

settings_bp = Blueprint('settings', __name__)
CLASS_OPTIONS = get_class_options(include_all_per_year=False)


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


@settings_bp.route('/api/settings/sync-term-dates', methods=['POST'])
def api_sync_term_dates():
    """Pull term dates from the school planning Google Sheet and save to term_dates.json."""
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401

    PLANNING_SHEET_ID = '1XsP5yEGnf8sJyXk8iEXqHEtw-NtCsMUFZLaHW4TWNhw'
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive',
    ]

    raw_creds = os.environ.get('GOOGLE_CREDENTIALS_JSON', '')
    if not raw_creds:
        return jsonify({'ok': False, 'error': 'GOOGLE_CREDENTIALS_JSON not set on server'})

    try:
        import json as _json
        import gspread
        from google.oauth2.service_account import Credentials
        from datetime import datetime, timedelta

        info   = _json.loads(raw_creds)
        creds  = Credentials.from_service_account_info(info, scopes=SCOPES)
        client = gspread.authorize(creds)
        sh     = client.open_by_key(PLANNING_SHEET_ID)
        ws     = sh.worksheet('TermDates')
        rows   = ws.get_all_records(default_blank='')
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Sheet read failed: {e}'})

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
        return jsonify({'ok': False, 'error': 'No valid rows found in TermDates sheet'})

    term_dates.sort(key=lambda w: w['iso'])

    from data_manager import _get_file, _put_file, _put_file_create
    path = 'data/term_dates.json'
    _, sha = _get_file(path)
    if sha is None:
        ok = _put_file_create(path, term_dates, 'Sync term dates from planning sheet')
    else:
        ok = _put_file(path, term_dates, sha, 'Sync term dates from planning sheet')

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
    from data_manager import YEAR_GROUP_CLASSES, get_class_options_for_year
    yr         = session.get('year_group', '4')
    yr_classes = YEAR_GROUP_CLASSES.get(yr, [])
    wc         = load_weekly_config()
    td         = load_term_dates()
    term_dates = term_dates_by_term(td)
    this_week  = current_week_ref(td)
    return render_template('settings.html',
        wc=wc, yr_classes=yr_classes, active_year=yr,
        class_options=get_class_options_for_year(yr, include_all=False),
        term_dates=term_dates,
        this_week=this_week)


@settings_bp.route('/api/settings/save', methods=['POST'])
def api_settings_save():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    body = request.get_json(force=True)

    wc = load_weekly_config()

    # ULS fields
    year_group  = body.get('year_group', '').strip()
    term        = body.get('term', '').strip()
    week        = body.get('week')
    lesson_ids  = body.get('lesson_ids', [])
    hl_mode     = body.get('hl_mode', 'single')
    hl_lesson_id = body.get('hl_lesson_id', '')
    selected_words = body.get('selected_words', [])

    if year_group:
        wc['year_group'] = year_group
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

    # Legacy week_ref override
    week_ref = body.get('week_ref', '').strip()
    if week_ref and not week:
        wc['week_ref'] = week_ref

    ok = save_weekly_config(wc)
    return jsonify({'ok': ok, 'error': None if ok else 'GitHub write failed'})

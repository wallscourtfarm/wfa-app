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

    # Legacy week_ref override
    week_ref = body.get('week_ref', '').strip()
    if week_ref and not week:
        wc['week_ref'] = week_ref

    ok = save_weekly_config(wc)
    return jsonify({'ok': ok, 'error': None if ok else 'GitHub write failed'})

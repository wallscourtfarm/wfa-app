from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import load_bee_pupils, save_bee_assessment, update_rule_confidence_from_bee, update_pupil_rule_confidence_from_bee, get_bee_weeks, YEAR_GROUP_CLASSES, _resolve_classes, get_class_options_for_year

bee_bp = Blueprint('bee', __name__)

@bee_bp.route('/spelling-bee')
def spelling_bee():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))
    yr           = session.get('year_group', '4')
    yr_classes   = YEAR_GROUP_CLASSES.get(yr, [])
    valid        = [f'Y{yr}_all'] + yr_classes
    cls          = request.args.get('cls', f'Y{yr}_all')
    if cls not in valid: cls = f'Y{yr}_all'
    group_filter = request.args.get('group', 'all')

    # Which week to mark against — independent of whatever Settings
    # currently has "live", so setting up a future week there doesn't pull
    # the rug out from under someone still marking an earlier week.
    bee_weeks, current_week_ref = get_bee_weeks(yr)
    selected_week = request.args.get('week', '') or current_week_ref

    # Resolve _all to the actual classes for this year
    class_ids = _resolve_classes(cls)
    pupils, rules_info, week_ref = [], {}, ''
    for cid in class_ids:
        p, ri, wr = load_bee_pupils(cid, selected_week)
        pupils += p
        if not rules_info: rules_info = ri
        if not week_ref:   week_ref   = wr

    if group_filter != 'all':
        pupils = [p for p in pupils if p['group'] == group_filter]

    pupils.sort(key=lambda p: p['first'].lower())

    class_options = get_class_options_for_year(yr)
    return render_template('bee.html', pupils=pupils, rules_info=rules_info,
                           week_ref=week_ref, group_filter=group_filter,
                           cls=cls, class_options=class_options, active_year=yr,
                           bee_weeks=bee_weeks, selected_week=selected_week)

@bee_bp.route('/api/bee/save', methods=['POST'])
def api_bee_save():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    body        = request.get_json(force=True)
    assessments = body.get('assessments', [])
    week_ref    = body.get('week_ref', '')
    if not assessments:
        return jsonify({'ok': False, 'error': 'Nothing to save'})

    # Group assessments by class — fall back to top-level cls if not on each assessment
    cls_from_body = body.get('cls', '')
    by_class = {}
    for a in assessments:
        c = a.get('cls', '') or cls_from_body
        by_class.setdefault(c, []).append(a)

    total_saved = 0
    for cls_id, ass_list in by_class.items():
        result = save_bee_assessment(cls_id, ass_list)
        if not result.get('ok'):
            return jsonify(result)
        total_saved += result.get('saved', 0)

    # Update rule confidence dots based on words marked correct per rule —
    # pinned to the week the page was actually marking against, not
    # whatever week Settings currently has live.
    update_rule_confidence_from_bee(assessments, week_ref)
    # Also build up each pupil's own rule confidence history week by week
    update_pupil_rule_confidence_from_bee(assessments, week_ref)

    return jsonify({'ok': True, 'saved': total_saved})

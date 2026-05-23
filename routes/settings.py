from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import load_weekly_config, save_weekly_config, list_plannable_rules, ALL_CLASSES

settings_bp = Blueprint('settings', __name__)
CLASS_OPTIONS = [('Y4_IM', 'Y4 IM'), ('Y4_WU', 'Y4 WU')]



@settings_bp.route('/api/debug/learners')
def api_debug_learners():
    if not session.get('authenticated'):
        return jsonify({'ok': False}), 401
    from data_manager import load_learners
    pupils = load_learners('Y4_IM')
    # Return first 3 pupils with key fields
    sample = [{'id': p.get('id'), 'first': p.get('first'),
               'pair_id': p.get('pair_id'), 'partner_name': p.get('partner_name')}
              for p in pupils[:3]]
    return jsonify({'ok': True, 'sample': sample})

@settings_bp.route('/settings')
def settings():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))
    wc      = load_weekly_config()
    rules   = list_plannable_rules()   # [(id_str, label), ...]
    return render_template('settings.html',
        wc=wc, rules=rules, class_options=CLASS_OPTIONS)


@settings_bp.route('/api/settings/save', methods=['POST'])
def api_settings_save():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    body      = request.get_json(force=True)
    week_ref  = body.get('week_ref', '').strip()
    classes   = body.get('classes', {})   # {cls_id: {main_rule_id, revision_rule_id}}

    wc = load_weekly_config()
    if week_ref:
        wc['week_ref'] = week_ref
    for cls_id, cfg in classes.items():
        wc.setdefault('classes', {}).setdefault(cls_id, {})
        if cfg.get('main_rule_id') is not None:
            wc['classes'][cls_id]['main_rule_id']     = cfg['main_rule_id']
        if cfg.get('revision_rule_id') is not None:
            wc['classes'][cls_id]['revision_rule_id'] = cfg['revision_rule_id']

    ok = save_weekly_config(wc)
    return jsonify({'ok': ok, 'error': None if ok else 'GitHub write failed'})

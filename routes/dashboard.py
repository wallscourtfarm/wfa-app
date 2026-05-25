import json
from flask import Blueprint, render_template, session, redirect, url_for, request
from data_manager import load_dashboard, TT_ORDER, ALL_CLASSES, get_class_options, get_class_options_for_year, get_ref_class

dash_bp = Blueprint('dash', __name__)
CLASS_OPTIONS = get_class_options()

@dash_bp.route('/dashboard')
def dashboard():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))
    yr  = session.get('year_group', '4')
    cls = request.args.get('cls', f'Y{yr}_all')
    yr  = session.get('year_group', '4')
    valid = [c[0] for c in get_class_options_for_year(yr)]
    if cls not in valid: cls = f'Y{yr}_all'
    data = load_dashboard(cls)
    if not data:
        return render_template('dashboard.html', error=True, cls=cls, class_options=get_class_options_for_year(session.get("year_group","4")))
    tt_labels = [f'×{t}' if t!='All' else 'All' for t in TT_ORDER]
    tt_values = [data['tt_dist'].get(t,0) for t in TT_ORDER]
    return render_template('dashboard.html',
        rows=data['rows'], stats=data['stats'],
        tt_labels=json.dumps(tt_labels), tt_values=json.dumps(tt_values),
        cls=cls, class_options=get_class_options_for_year(session.get("year_group","4")))

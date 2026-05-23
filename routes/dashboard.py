import json
from flask import Blueprint, render_template, session, redirect, url_for, request
from data_manager import load_dashboard, TT_ORDER, load_class

dash_bp = Blueprint('dash', __name__)

CLASSES = ['Y4_IM', 'Y4_WU']

@dash_bp.route('/')
@dash_bp.route('/dashboard')
def dashboard():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))
    cls = request.args.get('cls', 'Y4_IM')
    if cls not in CLASSES:
        cls = 'Y4_IM'
    data = load_dashboard(cls)
    if not data:
        return render_template('dashboard.html', error=True, cls=cls, classes=CLASSES)
    tt_labels = [f'×{t}' if t != 'All' else 'All' for t in TT_ORDER]
    tt_values = [data['tt_dist'].get(t, 0) for t in TT_ORDER]
    return render_template('dashboard.html',
        rows=data['rows'], stats=data['stats'],
        tt_labels=json.dumps(tt_labels), tt_values=json.dumps(tt_values),
        cls=cls, classes=CLASSES)

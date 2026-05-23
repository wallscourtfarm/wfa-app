from flask import Blueprint, render_template, session, redirect, url_for, request
from data_manager import load_learners, ALL_CLASSES

learners_bp = Blueprint('learners', __name__)
CLASS_OPTIONS = [('Y4_IM','Y4 IM'),('Y4_WU','Y4 WU')]

@learners_bp.route('/learners')
def learners():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))
    cls = request.args.get('cls','Y4_IM')
    if cls not in [c[0] for c in CLASS_OPTIONS]: cls='Y4_IM'
    pupils = load_learners(cls)
    return render_template('learners.html', pupils=pupils, cls=cls, class_options=CLASS_OPTIONS)

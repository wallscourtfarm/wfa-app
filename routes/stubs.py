from flask import Blueprint, render_template, session, redirect, url_for
stubs_bp = Blueprint('stubs', __name__)

def _auth():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))

@stubs_bp.route('/digital-ipad')
def digital_ipad():
    r = _auth()
    if r: return r
    return render_template('stub.html', title='Digital / iPad', icon='💻',
        description='Create iPad spelling sessions for pupils to self-assess. Results import automatically.',
        coming='Session creation and result import')

@stubs_bp.route('/classes')
def classes():
    r = _auth()
    if r: return r
    return render_template('stub.html', title='Classes', icon='👥',
        description='Manage class rosters, import CSV data and configure TT tracking.',
        coming='Class management and CSV import')



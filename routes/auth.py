import hmac
import logging
import os
from flask import Blueprint, render_template, request, redirect, url_for, session

auth_bp = Blueprint('auth', __name__)

# No built-in fallback: if APP_PASSWORD is not set on the server, nobody can log in
# (a default password in public code is a password for everyone). Changed 26.09.26.
APP_PASSWORD = os.environ.get('APP_PASSWORD') or ''
if not APP_PASSWORD:
    logging.getLogger(__name__).error('APP_PASSWORD is not set - login is disabled')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        submitted = request.form.get('password') or ''
        if APP_PASSWORD and hmac.compare_digest(submitted.encode(), APP_PASSWORD.encode()):
            session['authenticated'] = True
            return redirect(url_for('index'))
        error = 'Wrong password.'
    return render_template('login.html', error=error)


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

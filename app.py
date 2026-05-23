import os
from flask import Flask, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')

from routes.auth import auth_bp
from routes.tt import tt_bp

app.register_blueprint(auth_bp)
app.register_blueprint(tt_bp)


@app.route('/')
def index():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))
    return redirect(url_for('tt.tt_check'))


if __name__ == '__main__':
    app.run(debug=True)

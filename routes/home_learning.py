from flask import Blueprint, redirect, session

hl_bp = Blueprint('hl', __name__)


@hl_bp.route('/home-learning')
def home_learning():
    """Home Learning lives in the Streamlit generator. (The old in-app generator and its /api/hl/* routes were
    removed 18.10.26: nothing used them, and they were a second place a names file could reach a server.)"""
    yr = session.get('active_year', '')
    return redirect(f'https://spelling-homelearning.streamlit.app/?year={yr}' if yr else 'https://spelling-homelearning.streamlit.app/')

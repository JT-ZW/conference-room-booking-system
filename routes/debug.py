from flask import Blueprint, jsonify, session, current_app
from flask_login import login_required, current_user

debug_bp = Blueprint('debug', __name__)

@debug_bp.route('/debug/session')
def debug_session():
    return jsonify({
        'authenticated': current_user.is_authenticated,
        'user_id': getattr(current_user, 'id', None),
        'user_email': getattr(current_user, 'email', None),
        'session_keys': list(session.keys()),
        'has_supabase_session': 'supabase_session' in session,
        'session_permanent': session.permanent,
        'secret_key_set': bool(current_app.config.get('SECRET_KEY')),
        'environment': current_app.config.get('ENV', 'development'),
        'supabase_session_data': session.get('supabase_session', 'Not found')
    }) 
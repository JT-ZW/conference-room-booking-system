from flask import request, session
from flask_login import current_user
from datetime import datetime, timezone, timedelta

# Central Africa Time (CAT) UTC+2
CAT = timezone(timedelta(hours=2))
from datetime import datetime, UTC
from settings.config import SUPABASE_SERVICE_KEY, SUPABASE_URL
from supabase import create_client

# Initialize Supabase admin client
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY) if SUPABASE_SERVICE_KEY else None

def log_user_activity(
    activity_type,
    activity_description,
    resource_type=None,
    resource_id=None,
    status='success',
    metadata=None
):
    """
    Log user activity to the database. This function is designed to be non-blocking and safe.
    """
    try:
        if not current_user.is_authenticated and activity_type not in ['login_attempt', 'failed_login']:
            return
        user_id = None
        user_name = 'Anonymous'
        user_email = 'unknown@example.com'
        if current_user.is_authenticated:
            user_id = current_user.id
            user_name = f"{current_user.first_name} {current_user.last_name}".strip() or current_user.email
            user_email = current_user.email
        ip_address = None
        user_agent = None
        session_id = None
        if request:
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
            user_agent = request.headers.get('User-Agent', '')[:500]
        if session:
            session_id = session.get('session_id') or str(hash(str(session)))[:32]
        log_data = {
            'user_id': user_id,
            'user_name': user_name,
            'user_email': user_email,
            'activity_type': activity_type,
            'activity_description': activity_description,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'status': status,
            'metadata': metadata or {},
            'ip_address': ip_address,
            'user_agent': user_agent,
            'session_id': session_id,
            'timestamp': datetime.now(CAT).isoformat()
            'session_id': session_id
            # Note: created_at column has a default value in the database
        }
        if supabase_admin:
            supabase_admin.table('user_activity_log').insert(log_data).execute()
    except Exception as e:
        print(f"❌ ERROR: Failed to log user activity: {e}")

def log_authentication_activity(activity_type, email, success=True, additional_info=None):
    """
    Log authentication-related activity (login, logout, registration, etc.)
    """
    try:
        log_data = {
            'activity_type': activity_type,
            'email': email,
            'success': success,
            'additional_info': additional_info or {},
            'timestamp': datetime.now(CAT).isoformat()
            'additional_info': additional_info or {}
            # Note: created_at column has a default value in the database
        }
        if supabase_admin:
            supabase_admin.table('auth_activity_log').insert(log_data).execute()
    except Exception as e:
        print(f"❌ ERROR: Failed to log authentication activity: {e}") 
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Validate environment variables

def validate_environment():
    """Validate all required environment variables"""
    required_vars = {
        'SUPABASE_URL': os.environ.get('SUPABASE_URL'),
        'SUPABASE_ANON_KEY': os.environ.get('SUPABASE_ANON_KEY'),
    }
    missing_vars = [var for var, value in required_vars.items() if not value]
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        print(f"❌ {error_msg}")
        raise ValueError(error_msg)
    print("✅ All required environment variables are set")
    # Check optional but important variables
    service_key = os.environ.get('SUPABASE_SERVICE_KEY')
    if not service_key:
        print("⚠️ WARNING: SUPABASE_SERVICE_KEY not set. Some operations may fail due to RLS.")
    else:
        print("✅ Service key available for admin operations")
    return True

validate_environment()

# Flask app config
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'fallback-key-change-in-production-' + str(datetime.now().timestamp()))
    SESSION_COOKIE_SECURE = False  # Set to False for now, will be handled later
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)
    SESSION_REFRESH_EACH_REQUEST = True
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    WTF_CSRF_SSL_STRICT = False
    ACTIVITY_LOG_RETENTION_DAYS = int(os.environ.get('ACTIVITY_LOG_RETENTION_DAYS', 90))
    ACTIVITY_LOG_ENABLED = os.environ.get('ACTIVITY_LOG_ENABLED', 'true').lower() == 'true'

# Supabase config
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY') 
import functools
from flask import request, session
from flask_login import current_user
from datetime import datetime, timezone, timedelta

# Central Africa Time (CAT) UTC+2
CAT = timezone(timedelta(hours=2))
from datetime import datetime, UTC
from .logging import log_user_activity

def activity_logged(activity_type, description_template=None, resource_type=None, status='success'):
    """
    Decorator to automatically log activities for route functions.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.now(CAT)
            start_time = datetime.now(UTC)
            activity_status = status
            result = None
            error_info = None
            try:
                result = func(*args, **kwargs)
                if hasattr(result, 'status_code') and result.status_code >= 400:
                    activity_status = 'failed'
                elif isinstance(result, dict) and result.get('error'):
                    activity_status = 'failed'
            except Exception as e:
                activity_status = 'failed'
                error_info = str(e)
                raise
            finally:
                try:
                    if description_template:
                        if '{result}' in description_template:
                            description = description_template.format(result=str(result)[:200] if result else 'No result')
                        else:
                            description = description_template
                    else:
                        description = f"Executed {func.__name__}"
                    metadata = {
                        'function_name': func.__name__,
                        'execution_time_ms': int((datetime.now(CAT) - start_time).total_seconds() * 1000),
                        'execution_time_ms': int((datetime.now(UTC) - start_time).total_seconds() * 1000),
                        'args_count': len(args),
                        'kwargs_keys': list(kwargs.keys()) if kwargs else []
                    }
                    if error_info:
                        metadata['error'] = error_info
                    if hasattr(result, 'get') and result.get('id'):
                        resource_id = result.get('id')
                    else:
                        resource_id = kwargs.get('id') or (args[0] if args and isinstance(args[0], int) else None)
                    log_user_activity(
                        activity_type=activity_type,
                        activity_description=description,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        status=activity_status,
                        metadata=metadata
                    )
                except Exception:
                    pass
            return result
        return wrapper
    return decorator

def require_admin_or_manager(f):
    """Decorator to require admin or manager role"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['admin', 'manager']:
            from flask import flash, redirect, url_for
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('dashboard'))
            return redirect(url_for('dashboard.dashboard'))
        return f(*args, **kwargs)
    return decorated_function 
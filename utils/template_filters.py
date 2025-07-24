from datetime import datetime, timezone, timedelta

# Define CAT timezone
CAT = timezone(timedelta(hours=2))

def parse_datetime_filter(date_string):
    if isinstance(date_string, str):
        try:
            return datetime.fromisoformat(date_string.replace('Z', '+00:00')).replace(tzinfo=None)
        except (ValueError, AttributeError):
            return date_string
    return date_string

def format_datetime_filter(dt, format='%d %b %Y'):
    try:
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00')).replace(tzinfo=None)
        if isinstance(dt, datetime):
            return dt.strftime(format)
        return dt
    except Exception:
        return dt

def format_cat_datetime_filter(timestamp_str, format='%d %b %Y at %H:%M'):
    """Format timestamp in CAT timezone"""
    try:
        if isinstance(timestamp_str, str):
            # Parse the ISO timestamp
            if 'T' in timestamp_str or '+' in timestamp_str or 'Z' in timestamp_str:
                # Full ISO format with timezone info
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                # Simple datetime string (likely from database without timezone)
                dt = datetime.fromisoformat(timestamp_str)
            
            # For older records without timezone info, assume they are UTC and convert to CAT
            if dt.tzinfo is None:
                # Assume UTC for timezone-naive timestamps and convert to CAT
                dt = dt.replace(tzinfo=timezone.utc).astimezone(CAT)
            else:
                # Convert any timezone-aware timestamp to CAT
                dt = dt.astimezone(CAT)
            
            return dt.strftime(format)
        elif isinstance(timestamp_str, datetime):
            if timestamp_str.tzinfo is None:
                # Assume UTC for timezone-naive datetime objects
                timestamp_str = timestamp_str.replace(tzinfo=timezone.utc).astimezone(CAT)
            else:
                timestamp_str = timestamp_str.astimezone(CAT)
            return timestamp_str.strftime(format)
        return timestamp_str
    except Exception:
        return str(timestamp_str) if timestamp_str else ""

def calculate_total_filter(room_rate, addons_total):
    try:
        return float(room_rate or 0) + float(addons_total or 0)
    except Exception:
        return 0

def format_pricing_summary_filter(booking):
    try:
        return f"Room: {booking.get('room_name', '')}, Total: ${booking.get('total_price', 0):.2f}"
    except Exception:
        return ""

def money_filter(amount):
    try:
        if amount is None:
            return "$0.00"
        return f"${float(amount):.2f}"
    except (ValueError, TypeError):
        return "$0.00"

def duration_filter(hours):
    try:
        hours = float(hours)
        if hours < 1:
            minutes = int(hours * 60)
            return f"{minutes} minutes"
        elif hours == 1:
            return "1 hour"
        elif hours < 24:
            return f"{hours:.1f} hours"
        else:
            days = int(hours // 24)
            return f"{days} days"
    except Exception:
        return "-"

def booking_status_color_filter(status):
    colors = {
        'tentative': 'warning',
        'confirmed': 'success',
        'cancelled': 'danger',
        'completed': 'primary',
        'pending': 'secondary',
    }
    return colors.get(str(status).lower(), 'secondary')

def nl2br_filter(text):
    if not text:
        return ''
    return text.replace('\n', '<br>')

def safe_startswith_filter(text, prefix):
    if text is None or prefix is None:
        return False
    try:
        return str(text).startswith(str(prefix))
    except (AttributeError, TypeError):
        return False

def safe_string_filter(value, default=''):
    if value is None:
        return default
    try:
        return str(value)
    except (TypeError, ValueError):
        return default

def safe_contains_filter(text, substring):
    if text is None or substring is None:
        return False
    try:
        return str(substring).lower() in str(text).lower()
    except (AttributeError, TypeError):
        return False

def truncate_safe_filter(text, length=100, suffix='...'):
    if text is None:
        return ''
    try:
        text = str(text)
        if len(text) <= length:
            return text
        return text[:length] + suffix
    except (TypeError, ValueError):
        return ''

def default_if_none_filter(value, default='N/A'):
    return value if value is not None else default 

def format_currency_filter(amount):
    """Format amount as currency"""
    try:
        if amount is None:
            return "$0.00"
        return f"${float(amount):,.2f}"
    except (ValueError, TypeError):
        return "$0.00"

def format_percentage_filter(value, decimal_places=1):
    """Format value as percentage"""
    try:
        if value is None:
            return "0%"
        return f"{float(value):.{decimal_places}f}%"
    except (ValueError, TypeError):
        return "0%"

def time_ago_filter(dt):
    """Calculate time ago from datetime"""
    try:
        from datetime import datetime, UTC
        
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00')).replace(tzinfo=None)
        
        if not isinstance(dt, datetime):
            return "Unknown"
            
        now = datetime.now(UTC).replace(tzinfo=None)
        diff = now - dt
        
        if diff.days > 0:
            if diff.days == 1:
                return "1 day ago"
            elif diff.days < 7:
                return f"{diff.days} days ago"
            elif diff.days < 30:
                weeks = diff.days // 7
                return f"{weeks} week{'s' if weeks > 1 else ''} ago"
            else:
                months = diff.days // 30
                return f"{months} month{'s' if months > 1 else ''} ago"
        
        hours = diff.seconds // 3600
        if hours > 0:
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        
        minutes = diff.seconds // 60
        if minutes > 0:
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        
        return "Just now"
        
    except Exception as e:
        return "Unknown"

def days_until_filter(dt):
    """Calculate days until datetime"""
    try:
        from datetime import datetime, UTC
        
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00')).replace(tzinfo=None)
        
        if not isinstance(dt, datetime):
            return "Unknown"
            
        now = datetime.now(UTC).replace(tzinfo=None)
        diff = dt - now
        
        if diff.days > 0:
            if diff.days == 1:
                return "Tomorrow"
            elif diff.days < 7:
                return f"In {diff.days} days"
            elif diff.days < 30:
                weeks = diff.days // 7
                return f"In {weeks} week{'s' if weeks > 1 else ''}"
            else:
                months = diff.days // 30
                return f"In {months} month{'s' if months > 1 else ''}"
        elif diff.days == 0:
            hours = diff.seconds // 3600
            if hours > 0:
                return f"In {hours} hour{'s' if hours > 1 else ''}"
            minutes = diff.seconds // 60
            if minutes > 0:
                return f"In {minutes} minute{'s' if minutes > 1 else ''}"
            return "Now"
        else:
            return "Past due"
            
    except Exception as e:
        return "Unknown"
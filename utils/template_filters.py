from datetime import datetime

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
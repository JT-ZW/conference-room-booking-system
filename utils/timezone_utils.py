"""
Timezone utilities for Central Africa Time (CAT) handling
"""
import pytz
from datetime import datetime

# Define CAT timezone
CAT = pytz.timezone('Africa/Harare')  # CAT timezone (UTC+2)

def get_cat_now():
    """Get current time in CAT timezone"""
    return datetime.now(CAT)

def convert_utc_to_cat(utc_dt):
    """Convert UTC datetime to CAT"""
    if utc_dt is None:
        return None
    
    if isinstance(utc_dt, str):
        # Parse ISO format string
        try:
            utc_dt = datetime.fromisoformat(utc_dt.replace('Z', '+00:00'))
        except:
            return utc_dt
    
    # If naive datetime, assume UTC
    if utc_dt.tzinfo is None:
        utc_dt = pytz.UTC.localize(utc_dt)
    
    return utc_dt.astimezone(CAT)

def convert_cat_to_utc(cat_dt):
    """Convert CAT datetime to UTC"""
    if cat_dt is None:
        return None
    
    if isinstance(cat_dt, str):
        # Parse ISO format string
        try:
            cat_dt = datetime.fromisoformat(cat_dt.replace('Z', '+00:00'))
        except:
            return cat_dt
    
    # If naive datetime, assume CAT
    if cat_dt.tzinfo is None:
        cat_dt = CAT.localize(cat_dt)
    
    return cat_dt.astimezone(pytz.UTC)

def format_cat_datetime(dt, format_string='%Y-%m-%d %H:%M:%S'):
    """Format datetime in CAT timezone"""
    if dt is None:
        return ''
    
    cat_dt = convert_utc_to_cat(dt)
    return cat_dt.strftime(format_string)

def get_cat_business_hours():
    """Get business hours in CAT"""
    return {
        'start_hour': 6,  # 6 AM CAT
        'end_hour': 23,   # 11 PM CAT
        'timezone': 'CAT (UTC+2)'
    }

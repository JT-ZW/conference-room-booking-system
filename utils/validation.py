from datetime import datetime, timedelta, UTC

def safe_float_conversion(value, default=0.0):
    """Safely convert value to float with fallback"""
    try:
        if value is None:
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int_conversion(value, default=0):
    """Safely convert value to int with fallback"""
    try:
        if value is None:
            return default
        return int(value)
    except (ValueError, TypeError):
        return default

def convert_datetime_strings(data, datetime_fields=['start_time', 'end_time', 'created_at', 'updated_at', 'check_in', 'check_out']):
    """Convert ISO datetime strings in a dict to datetime objects."""
    if isinstance(data, dict):
        converted = data.copy()
        for field in datetime_fields:
            if field in converted and isinstance(converted[field], str):
                try:
                    converted[field] = datetime.fromisoformat(converted[field].replace('Z', '+00:00')).replace(tzinfo=None)
                except (ValueError, AttributeError):
                    pass
        return converted
    return data

def validate_booking_times(start_time, end_time):
    """Validate booking start and end times with multi-day support."""
    errors = []
    try:
        if end_time <= start_time:
            errors.append("End time must be after start time")
        if start_time < datetime.now(UTC):
            errors.append("Booking cannot be scheduled in the past")
        max_future = datetime.now(UTC) + timedelta(days=365)
        if start_time > max_future:
            errors.append("Booking cannot be scheduled more than 1 year in advance")
        
        # Calculate duration in days and hours
        duration = end_time - start_time
        duration_days = duration.days
        duration_hours = duration.total_seconds() / 3600
        
        # Allow multi-day bookings (up to 30 days for conferences/events)
        if duration_days > 30:
            errors.append("Bookings cannot exceed 30 days")
        
        # For single day bookings, still check business hours
        if duration_days == 0:
            if start_time.hour < 6 or start_time.hour > 22:
                errors.append("Same-day bookings must start within business hours (6 AM - 10 PM)")
            if end_time.hour < 6 or end_time.hour > 23:
                errors.append("Same-day bookings must end within business hours (6 AM - 11 PM)")
            # Remove 12-hour limit for single day bookings to allow all-day events
            if duration_hours > 24:
                errors.append("Single-day bookings cannot exceed 24 hours")
        
        # Minimum duration check
        if duration_hours < 0.5:
            errors.append("Bookings must be at least 30 minutes long")
            
    except Exception:
        errors.append("Invalid date/time values")
    return errors

def validate_booking_capacity(room_id, attendees):
    """Stub for booking capacity validation (implement as needed)."""
    # This function can be expanded to check room capacity from DB
    return [] 
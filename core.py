import os
from flask import session, flash, render_template, redirect, url_for
from datetime import datetime, UTC, timedelta, timezone
from supabase import create_client, Client
from settings.config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY
from flask_login import UserMixin, current_user
from utils.validation import convert_datetime_strings, safe_float_conversion, safe_int_conversion
from decimal import Decimal
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os

# Initialize Supabase clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
if SUPABASE_SERVICE_KEY:
    supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
else:
    supabase_admin = supabase

# ===============================
# EMAIL CONFIGURATION
# ===============================

# Email settings - you can add these to your environment variables
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USER = os.getenv('EMAIL_USER', 'your-email@gmail.com')  # Replace with your email
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', 'your-app-password')  # Replace with app password
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'

# Test email address for development
TEST_EMAIL = os.getenv('TEST_EMAIL', 'your-test-email@gmail.com')  # Replace with your test email

# CAT (Central Africa Time) timezone - UTC+2
CAT = timezone(timedelta(hours=2))

# ===============================
# EMAIL FUNCTIONS
# ===============================

def send_email(to_email, subject, body_html, body_text=None):
    """
    Send an email using SMTP with HTML and optional text content.
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        body_html (str): HTML body content
        body_text (str, optional): Plain text body content
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = EMAIL_USER
        msg['To'] = to_email

        # Create text and HTML parts
        if body_text:
            part1 = MIMEText(body_text, 'plain')
            msg.attach(part1)
        
        part2 = MIMEText(body_html, 'html')
        msg.attach(part2)

        # Create SMTP session
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()  # Enable encryption
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        
        # Send email
        server.send_message(msg)
        server.quit()
        
        print(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        print(f"Failed to send email to {to_email}: {str(e)}")
        return False

def get_booking_confirmation_html(booking_data):
    """
    Generate HTML content for booking confirmation email.
    
    Args:
        booking_data (dict): Booking information
    
    Returns:
        str: HTML email content
    """
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .booking-details {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .footer {{ background-color: #f1f1f1; padding: 10px; text-align: center; font-size: 12px; }}
            .status-confirmed {{ color: #4CAF50; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🎉 Booking Confirmed!</h1>
        </div>
        
        <div class="content">
            <p>Dear {booking_data.get('client_name', 'Valued Customer')},</p>
            
            <p>Your booking has been <span class="status-confirmed">CONFIRMED</span>! Here are the details:</p>
            
            <div class="booking-details">
                <h3>📋 Booking Details</h3>
                <p><strong>Booking ID:</strong> #{booking_data.get('id', 'N/A')}</p>
                <p><strong>Client:</strong> {booking_data.get('client_name', 'N/A')}</p>
                <p><strong>Room/Venue:</strong> {booking_data.get('room_name', 'N/A')}</p>
                <p><strong>Start:</strong> {booking_data.get('start_time', 'N/A')}</p>
                <p><strong>End:</strong> {booking_data.get('end_time', 'N/A')}</p>
                <p><strong>Purpose:</strong> {booking_data.get('purpose', 'N/A')}</p>
                <p><strong>Status:</strong> <span class="status-confirmed">Confirmed</span></p>
                {f"<p><strong>Notes:</strong> {booking_data.get('notes', '')}</p>" if booking_data.get('notes') else ""}
            </div>
            
            <p>If you need to make any changes or have questions, please contact us immediately.</p>
            
            <p>Thank you for choosing our venue!</p>
        </div>
        
        <div class="footer">
            <p>This is an automated message. Please do not reply to this email.</p>
            <p>Generated on {datetime.now(CAT).strftime('%Y-%m-%d at %H:%M %Z')}</p>
        </div>
    </body>
    </html>
    """
    
    return html_template

def send_booking_confirmation_email(booking_data):
    """
    Send booking confirmation email for confirmed bookings.
    
    Args:
        booking_data (dict): Booking information including client details
    
    Returns:
        bool: True if email sent successfully
    """
    try:
        # Only send confirmation emails for confirmed bookings
        if booking_data.get('status') != 'confirmed':
            print(f"Skipping email for booking {booking_data.get('id')} - status is {booking_data.get('status')}")
            return False
        
        # For now, send to test email only
        # Later you can modify this to send to client email: booking_data.get('client_email')
        to_email = TEST_EMAIL
        
        subject = f"Booking Confirmation #{booking_data.get('id')} - {booking_data.get('room_name')}"
        
        # Generate HTML content
        html_body = get_booking_confirmation_html(booking_data)
        
        # Generate plain text version
        text_body = f"""
Booking Confirmed!

Dear {booking_data.get('client_name', 'Valued Customer')},

Your booking has been CONFIRMED! Here are the details:

Booking ID: #{booking_data.get('id', 'N/A')}
Client: {booking_data.get('client_name', 'N/A')}
Room/Venue: {booking_data.get('room_name', 'N/A')}
Start: {booking_data.get('start_time', 'N/A')}
End: {booking_data.get('end_time', 'N/A')}
Purpose: {booking_data.get('purpose', 'N/A')}
Status: Confirmed
{f"Notes: {booking_data.get('notes', '')}" if booking_data.get('notes') else ""}

If you need to make any changes or have questions, please contact us immediately.

Thank you for choosing our venue!

This is an automated message.
Generated on {datetime.now(CAT).strftime('%Y-%m-%d at %H:%M %Z')}
        """
        
        return send_email(to_email, subject, html_body, text_body)
        
    except Exception as e:
        print(f"Error sending booking confirmation email: {str(e)}")
        return False

def get_daily_report_html(report_data):
    """
    Generate HTML content for daily booking report.
    
    Args:
        report_data (dict): Report data with bookings and statistics
    
    Returns:
        str: HTML email content
    """
    today = datetime.now(CAT).strftime('%Y-%m-%d')
    
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #2196F3; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .stats {{ display: flex; justify-content: space-around; margin: 20px 0; }}
            .stat-box {{ background-color: #f0f8ff; padding: 15px; border-radius: 5px; text-align: center; flex: 1; margin: 0 10px; }}
            .stat-number {{ font-size: 24px; font-weight: bold; color: #2196F3; }}
            .bookings-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            .bookings-table th, .bookings-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            .bookings-table th {{ background-color: #f2f2f2; }}
            .status-confirmed {{ color: #4CAF50; font-weight: bold; }}
            .status-tentative {{ color: #FF9800; font-weight: bold; }}
            .status-cancelled {{ color: #f44336; font-weight: bold; }}
            .footer {{ background-color: #f1f1f1; padding: 10px; text-align: center; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 Daily Booking Report</h1>
            <h2>{today}</h2>
        </div>
        
        <div class="content">
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-number">{report_data.get('total_bookings', 0)}</div>
                    <div>Total Bookings</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{report_data.get('confirmed_bookings', 0)}</div>
                    <div>Confirmed</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{report_data.get('tentative_bookings', 0)}</div>
                    <div>Tentative</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{report_data.get('cancelled_bookings', 0)}</div>
                    <div>Cancelled</div>
                </div>
            </div>
            
            <h3>📅 Today's Bookings</h3>
            
            {get_bookings_table_html(report_data.get('today_bookings', []))}
            
            <h3>📈 Tomorrow's Bookings Preview</h3>
            
            {get_bookings_table_html(report_data.get('tomorrow_bookings', []))}
            
        </div>
        
        <div class="footer">
            <p>Daily report generated automatically at 5:00 PM CAT</p>
            <p>Generated on {datetime.now(CAT).strftime('%Y-%m-%d at %H:%M %Z')}</p>
        </div>
    </body>
    </html>
    """
    
    return html_template

def get_bookings_table_html(bookings):
    """
    Generate HTML table for bookings list.
    
    Args:
        bookings (list): List of booking dictionaries
    
    Returns:
        str: HTML table content
    """
    if not bookings:
        return "<p>No bookings scheduled.</p>"
    
    table_html = """
    <table class="bookings-table">
        <thead>
            <tr>
                <th>ID</th>
                <th>Client</th>
                <th>Room</th>
                <th>Start Time</th>
                <th>End Time</th>
                <th>Purpose</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for booking in bookings:
        status_class = f"status-{booking.get('status', 'tentative')}"
        table_html += f"""
        <tr>
            <td>#{booking.get('id', 'N/A')}</td>
            <td>{booking.get('client_name', 'N/A')}</td>
            <td>{booking.get('room_name', 'N/A')}</td>
            <td>{booking.get('start_time', 'N/A')}</td>
            <td>{booking.get('end_time', 'N/A')}</td>
            <td>{booking.get('purpose', 'N/A')}</td>
            <td><span class="{status_class}">{booking.get('status', 'tentative').title()}</span></td>
        </tr>
        """
    
    table_html += """
        </tbody>
    </table>
    """
    
    return table_html

def generate_daily_report_data():
    """
    Generate data for the daily report.
    
    Returns:
        dict: Report data with bookings and statistics
    """
    try:
        today = datetime.now(CAT).date()
        tomorrow = today + timedelta(days=1)
        
        # Get today's bookings
        today_response = supabase.table("bookings").select(
            "*, clients(name), rooms(name)"
        ).gte("start_time", today.isoformat()).lt("start_time", tomorrow.isoformat()).execute()
        
        # Get tomorrow's bookings
        day_after_tomorrow = tomorrow + timedelta(days=1)
        tomorrow_response = supabase.table("bookings").select(
            "*, clients(name), rooms(name)"
        ).gte("start_time", tomorrow.isoformat()).lt("start_time", day_after_tomorrow.isoformat()).execute()
        
        # Process today's bookings
        today_bookings = []
        confirmed_count = 0
        tentative_count = 0
        cancelled_count = 0
        
        for booking in today_response.data:
            booking_data = {
                'id': booking.get('id'),
                'client_name': booking.get('clients', {}).get('name') if booking.get('clients') else 'Unknown',
                'room_name': booking.get('rooms', {}).get('name') if booking.get('rooms') else 'Unknown',
                'start_time': booking.get('start_time'),
                'end_time': booking.get('end_time'),
                'purpose': booking.get('purpose'),
                'status': booking.get('status', 'tentative')
            }
            today_bookings.append(booking_data)
            
            # Count by status
            status = booking.get('status', 'tentative')
            if status == 'confirmed':
                confirmed_count += 1
            elif status == 'cancelled':
                cancelled_count += 1
            else:
                tentative_count += 1
        
        # Process tomorrow's bookings
        tomorrow_bookings = []
        for booking in tomorrow_response.data:
            booking_data = {
                'id': booking.get('id'),
                'client_name': booking.get('clients', {}).get('name') if booking.get('clients') else 'Unknown',
                'room_name': booking.get('rooms', {}).get('name') if booking.get('rooms') else 'Unknown',
                'start_time': booking.get('start_time'),
                'end_time': booking.get('end_time'),
                'purpose': booking.get('purpose'),
                'status': booking.get('status', 'tentative')
            }
            tomorrow_bookings.append(booking_data)
        
        return {
            'total_bookings': len(today_bookings),
            'confirmed_bookings': confirmed_count,
            'tentative_bookings': tentative_count,
            'cancelled_bookings': cancelled_count,
            'today_bookings': today_bookings,
            'tomorrow_bookings': tomorrow_bookings
        }
        
    except Exception as e:
        print(f"Error generating daily report data: {str(e)}")
        return {
            'total_bookings': 0,
            'confirmed_bookings': 0,
            'tentative_bookings': 0,
            'cancelled_bookings': 0,
            'today_bookings': [],
            'tomorrow_bookings': []
        }

def send_daily_report():
    """
    Generate and send the daily booking report.
    
    Returns:
        bool: True if report sent successfully
    """
    try:
        print(f"Generating daily report at {datetime.now(CAT).strftime('%Y-%m-%d %H:%M %Z')}")
        
        # Generate report data
        report_data = generate_daily_report_data()
        
        # For now, send to test email only
        to_email = TEST_EMAIL
        
        today = datetime.now(CAT).strftime('%Y-%m-%d')
        subject = f"Daily Booking Report - {today}"
        
        # Generate HTML content
        html_body = get_daily_report_html(report_data)
        
        # Generate plain text version
        text_body = f"""
Daily Booking Report - {today}

Statistics:
- Total Bookings: {report_data.get('total_bookings', 0)}
- Confirmed: {report_data.get('confirmed_bookings', 0)}
- Tentative: {report_data.get('tentative_bookings', 0)}
- Cancelled: {report_data.get('cancelled_bookings', 0)}

Today's Bookings: {len(report_data.get('today_bookings', []))} bookings
Tomorrow's Bookings: {len(report_data.get('tomorrow_bookings', []))} bookings

Report generated automatically at 5:00 PM CAT
Generated on {datetime.now(CAT).strftime('%Y-%m-%d at %H:%M %Z')}
        """
        
        return send_email(to_email, subject, html_body, text_body)
        
    except Exception as e:
        print(f"Error sending daily report: {str(e)}")
        return False

def get_booking_details_for_email(booking_id, booking_data):
    """
    Get booking details formatted for email.
    
    Args:
        booking_id (int): Booking ID
        booking_data (dict): Original booking data
    
    Returns:
        dict: Formatted booking data for email
    """
    try:
        # Get room name
        room_name = "Unknown Room"
        if booking_data.get('room_id'):
            room_response = supabase.table('rooms').select('name').eq('id', booking_data['room_id']).execute()
            if room_response.data:
                room_name = room_response.data[0]['name']
        
        # Format datetime strings for email
        start_time_formatted = booking_data['start_time'].strftime('%Y-%m-%d %H:%M') if hasattr(booking_data['start_time'], 'strftime') else str(booking_data['start_time'])
        end_time_formatted = booking_data['end_time'].strftime('%Y-%m-%d %H:%M') if hasattr(booking_data['end_time'], 'strftime') else str(booking_data['end_time'])
        
        return {
            'id': booking_id,
            'client_name': booking_data.get('client_name', 'Unknown'),
            'room_name': room_name,
            'start_time': start_time_formatted,
            'end_time': end_time_formatted,
            'purpose': booking_data.get('event_type', 'Event').replace('_', ' ').title(),
            'status': booking_data.get('status', 'confirmed'),
            'notes': booking_data.get('notes', ''),
            'client_email': booking_data.get('client_email', '')
        }
        
    except Exception as e:
        print(f"Error formatting booking details for email: {str(e)}")
        return {
            'id': booking_id,
            'client_name': booking_data.get('client_name', 'Unknown'),
            'room_name': 'Unknown Room',
            'start_time': str(booking_data.get('start_time', 'Unknown')),
            'end_time': str(booking_data.get('end_time', 'Unknown')),
            'purpose': booking_data.get('event_type', 'Event'),
            'status': booking_data.get('status', 'confirmed'),
            'notes': booking_data.get('notes', ''),
            'client_email': booking_data.get('client_email', '')
        }

# ===============================
# BOOKING AUDIT TRAIL FUNCTIONS
# ===============================

def log_booking_change(booking_id, action_type, field_changed=None, old_value=None, new_value=None, change_summary=None):
    """
    Log a change to a booking for audit trail purposes.
    
    Args:
        booking_id (int): The ID of the booking that was changed
        action_type (str): Type of action (created, updated, status_changed, cancelled)
        field_changed (str, optional): Specific field that was changed
        old_value (str, optional): Previous value
        new_value (str, optional): New value
        change_summary (str, optional): Human-readable description of the change
    """
    try:
        from flask import request
        from flask_login import current_user
        
        # Get user information
        user_id = None
        user_name = 'System'
        if hasattr(current_user, 'id') and current_user.is_authenticated:
            user_id = current_user.id
            user_name = getattr(current_user, 'username', current_user.id)
        
        # Get request information
        ip_address = None
        user_agent = None
        if request:
            ip_address = request.remote_addr
            user_agent = request.headers.get('User-Agent', '')[:500]  # Limit length
        
        # Prepare audit record
        audit_record = {
            'booking_id': booking_id,
            'user_id': user_id,
            'user_name': user_name,
            'action_type': action_type,
            'field_changed': field_changed,
            'old_value': str(old_value) if old_value is not None else None,
            'new_value': str(new_value) if new_value is not None else None,
            'change_summary': change_summary or f"{action_type.replace('_', ' ').title()} booking",
            'ip_address': ip_address,
            'user_agent': user_agent,
            'created_at': datetime.now(CAT).isoformat()
        }
        
        # Insert audit record
        result = supabase_admin.table('booking_audit_trail').insert(audit_record).execute()
        
        if result.data:
            print(f"✅ Audit trail logged: {action_type} for booking {booking_id}")
        else:
            print(f"⚠️ Failed to log audit trail for booking {booking_id}")
            
    except Exception as e:
        print(f"❌ ERROR: Failed to log booking audit trail: {e}")

def compare_booking_data(old_data, new_data):
    """
    Compare old and new booking data to identify changes.
    
    Args:
        old_data (dict): Original booking data
        new_data (dict): Updated booking data
        
    Returns:
        list: List of changes with field names, old values, and new values
    """
    changes = []
    
    # Fields to track for changes
    tracked_fields = {
        'status': 'Status',
        'room_id': 'Room',
        'start_time': 'Start Time',
        'end_time': 'End Time',
        'attendees': 'Number of Attendees',
        'notes': 'Notes',
        'total_price': 'Total Price',
        'client_name': 'Client Name',
        'company_name': 'Company Name',
        'client_email': 'Client Email',
        'title': 'Event Title'
    }
    
    for field, display_name in tracked_fields.items():
        old_value = old_data.get(field)
        new_value = new_data.get(field)
        
        # Handle different data types and formatting
        if field in ['start_time', 'end_time']:
            # Format datetime for comparison
            old_value = safe_format_datetime_for_comparison(old_value)
            new_value = safe_format_datetime_for_comparison(new_value)
        elif field == 'total_price':
            # Format currency for comparison
            old_value = f"${float(old_value or 0):.2f}"
            new_value = f"${float(new_value or 0):.2f}"
        elif field == 'room_id':
            # Get room names for better readability
            old_value = get_room_name_by_id(old_value) if old_value else 'None'
            new_value = get_room_name_by_id(new_value) if new_value else 'None'
        
        # Compare values
        if str(old_value or '').strip() != str(new_value or '').strip():
            changes.append({
                'field': field,
                'field_display': display_name,
                'old_value': old_value,
                'new_value': new_value
            })
    
    return changes

def safe_format_datetime_for_comparison(dt_value):
    """Format datetime for consistent comparison"""
    if not dt_value:
        return None
    
    try:
        if isinstance(dt_value, str):
            dt = datetime.fromisoformat(dt_value.replace('Z', '+00:00'))
        else:
            dt = dt_value
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return str(dt_value)

def get_room_name_by_id(room_id):
    """Get room name by ID for audit trail"""
    try:
        if not room_id:
            return None
        result = supabase_admin.table('rooms').select('name').eq('id', room_id).execute()
        if result.data:
            return result.data[0]['name']
        return f"Room ID: {room_id}"
    except:
        return f"Room ID: {room_id}"

def get_booking_audit_trail(booking_id, limit=50):
    """
    Get audit trail for a specific booking.
    
    Args:
        booking_id (int): The booking ID
        limit (int): Maximum number of records to return
        
    Returns:
        list: List of audit trail records
    """
    try:
        result = supabase_admin.table('booking_audit_trail')\
            .select('*')\
            .eq('booking_id', booking_id)\
            .order('created_at', desc=True)\
            .limit(limit)\
            .execute()
        
        if result.data:
            # Format the data for display
            formatted_records = []
            for record in result.data:
                # Parse the timestamp
                try:
                    created_at = datetime.fromisoformat(record['created_at'].replace('Z', '+00:00'))
                    formatted_time = created_at.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    formatted_time = record['created_at']
                
                formatted_record = {
                    'id': record['id'],
                    'user_name': record['user_name'] or 'System',
                    'action_type': record['action_type'],
                    'field_changed': record['field_changed'],
                    'old_value': record['old_value'],
                    'new_value': record['new_value'],
                    'change_summary': record['change_summary'],
                    'created_at': formatted_time,
                    'ip_address': record.get('ip_address'),
                    'time_ago': get_time_ago(record['created_at'])
                }
                formatted_records.append(formatted_record)
            
            return formatted_records
        
        return []
        
    except Exception as e:
        error_msg = str(e)
        if 'does not exist' in error_msg:
            print(f"⚠️ WARNING: Booking audit trail table not found. Please create it first.")
            return None  # Return None to indicate table doesn't exist
        else:
            print(f"❌ ERROR: Failed to get booking audit trail: {e}")
            return []

def get_time_ago(timestamp_str):
    """Get human-readable time ago string"""
    try:
        # Parse the timestamp - it should be in CAT timezone now
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        
        # If the timestamp doesn't have timezone info, assume it's in CAT
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=CAT)
        
        # Convert both timestamps to CAT for consistent comparison
        now = datetime.now(CAT)
        if dt.tzinfo != CAT:
            dt = dt.astimezone(CAT)
        
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "Just now"
    except:
        return ""

# ===============================
# UTILITY FUNCTIONS
# ===============================

def safe_str(value):
    """Safely convert value to string, handling None"""
    if value is None:
        return ''
    return str(value).strip()

def safe_str_lower(value):
    """Safely convert value to lowercase string, handling None"""
    return safe_str(value).lower()

# ===============================
# USER MODEL
# ===============================

class User(UserMixin):
    """User class that works with Supabase Auth"""
    def __init__(self, user_data):
        self.id = user_data.get('id')
        self.email = user_data.get('email')
        self.user_metadata = user_data.get('user_metadata', {})
        self.app_metadata = user_data.get('app_metadata', {})
        self.profile = self.get_profile()

    def get_profile(self):
        """Get user profile from Supabase users table"""
        try:
            response = supabase_admin.table('users').select('*').eq('id', self.id).execute()
            return response.data[0] if response.data else {}
        except:
            return {}

    @property
    def first_name(self):
        return self.profile.get('first_name', '')

    @property
    def last_name(self):
        return self.profile.get('last_name', '')

    @property
    def role(self):
        return self.profile.get('role', 'staff')

    @property
    def username(self):
        return self.profile.get('username', self.email.split('@')[0])

    @property
    def is_active(self):
        return self.profile.get('is_active', True)

    def get_id(self):
        return str(self.id)

# ===============================
# DATABASE HELPERS
# ===============================

def supabase_select(table_name, columns="*", filters=None, order_by=None, limit=None):
    """Select data from Supabase table"""
    try:
        query = supabase_admin.table(table_name).select(columns)
        
        if filters:
            for filter_item in filters:
                if len(filter_item) == 3:
                    column, operator, value = filter_item
                    if operator == 'eq':
                        query = query.eq(column, value)
                    elif operator == 'neq':
                        query = query.neq(column, value)
                    elif operator == 'gte':
                        query = query.gte(column, value)
                    elif operator == 'lte':
                        query = query.lte(column, value)
                    elif operator == 'gt':
                        query = query.gt(column, value)
                    elif operator == 'lt':
                        query = query.lt(column, value)
        
        if order_by:
            query = query.order(order_by)
            
        if limit:
            query = query.limit(limit)
        
        response = query.execute()
        return response.data if response.data else []
            
    except Exception as e:
        print(f"❌ ERROR: Failed to query table '{table_name}': {e}")
        return []

def supabase_insert(table_name, data):
    """Insert data into Supabase table"""
    try:
        response = supabase_admin.table(table_name).insert(data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Insert error: {e}")
        return None

def supabase_update(table_name, data, filters):
    """Update data in Supabase table"""
    try:
        query = supabase_admin.table(table_name).update(data)
        
        for filter_item in filters:
            if len(filter_item) == 3:
                column, operator, value = filter_item
                if operator == 'eq':
                    query = query.eq(column, value)
        
        response = query.execute()
        return response.data if response.data else []
                
    except Exception as e:
        print(f"Update error: {e}")
        return []

def supabase_delete(table_name, filters):
    """Delete data from Supabase table"""
    try:
        query = supabase_admin.table(table_name)
        
        for filter_item in filters:
            if len(filter_item) == 3:
                column, operator, value = filter_item
                if operator == 'eq':
                    query = query.eq(column, value)
        
        query.delete().execute()
        return True
    except Exception as e:
        print(f"Delete error: {e}")
        return False

# ===============================
# AUTHENTICATION
# ===============================

def authenticate_user(email, password):
    """Authenticate user with Supabase (optimized for version 2.16.0)"""
    try:
        # Use the modern sign_in_with_password method (available in 2.16.0)
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        # Handle the response structure for newer Supabase versions
        if response.user and response.session:
            # Clear and set up Flask session
            session.clear()
            session.permanent = True
            
            # Store session data
            session_data = {
                'access_token': response.session.access_token,
                'refresh_token': response.session.refresh_token,
                'user_id': response.user.id
            }
            
            session['supabase_session'] = session_data
            session['created_at'] = datetime.now(UTC).isoformat()
            session['user_id'] = response.user.id
            session['user_email'] = response.user.email
            session.modified = True
            
            # Create User object with proper data structure
            user_dict = {
                'id': response.user.id,
                'email': response.user.email,
                'user_metadata': getattr(response.user, 'user_metadata', {}),
                'app_metadata': getattr(response.user, 'app_metadata', {})
            }
            
            return User(user_dict)
        
        return None
            
    except Exception as e:
        print(f"Authentication error: {e}")
        return None

def create_user_supabase(email, password, first_name, last_name, role='staff'):
    """Create new user in Supabase"""
    try:
        # Create auth user
        auth_response = supabase_admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "first_name": first_name,
                "last_name": last_name,
                "role": role
            }
        })
        
        if auth_response.user:
            # Create user profile
            profile_data = {
                'id': auth_response.user.id,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'username': email.split('@')[0],
                'role': role,
                'is_active': True,
                'created_at': datetime.now(UTC).isoformat()
            }
            
            profile_response = supabase_admin.table('users').insert(profile_data).execute()
            
            if profile_response.data:
                return True, None
            else:
                # Cleanup on failure
                try:
                    supabase_admin.auth.admin.delete_user(auth_response.user.id)
                except:
                    pass
                return False, "Failed to create user profile"
        
        return False, "Failed to create auth user"
        
    except Exception as e:
        error_message = str(e).lower()
        if 'already registered' in error_message or 'already exists' in error_message:
            return False, "Email already registered"
        elif 'password' in error_message:
            return False, "Password does not meet requirements"
        elif 'email' in error_message and 'invalid' in error_message:
            return False, "Invalid email format"
        else:
            return False, "Registration failed"

# ===============================
# ACTIVITY LOGGING
# ===============================

def safe_log_user_activity(activity_type, description, resource_type=None, resource_id=None, metadata=None):
    """Log user activity (simplified version)"""
    try:
        activity_data = {
            'activity_type': activity_type,
            'description': description,
            'created_at': datetime.now(UTC).isoformat()
        }
        
        if current_user and current_user.is_authenticated:
            activity_data['user_id'] = str(current_user.id)
        
        if resource_type:
            activity_data['resource_type'] = resource_type
        if resource_id:
            activity_data['resource_id'] = str(resource_id)
        if metadata and isinstance(metadata, dict):
            activity_data['metadata'] = metadata
        
        # Try to insert into activity log table if it exists
        try:
            supabase_admin.table('user_activity_log').insert(activity_data).execute()
        except:
            # If table doesn't exist, just log to console
            print(f"📝 ACTIVITY: {activity_type} - {description}")
        
        return True
        
    except Exception as e:
        print(f"Activity logging error: {e}")
        return True  # Don't fail operations due to logging issues

# ===============================
# CLIENT MANAGEMENT
# ===============================

def get_all_clients_from_db():
    """Get all clients from database"""
    try:
        response = supabase_admin.table('clients').select('*').order('company_name').execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch clients: {e}")
        return []

def get_client_by_id_from_db(client_id):
    """Get specific client by ID"""
    try:
        response = supabase_admin.table('clients').select('*').eq('id', client_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch client {client_id}: {e}")
        return None

def get_client_bookings_from_db(client_id):
    """Get all bookings for a specific client"""
    try:
        response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity)
        """).eq('client_id', client_id).order('start_time', desc=True).execute()
        
        if response.data:
            return convert_datetime_strings(response.data)
        return []
            
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch client bookings: {e}")
        return []

def create_client_in_db(client_data):
    """Create a new client"""
    try:
        # Ensure required fields
        required_fields = ['contact_person', 'email']
        for field in required_fields:
            if not client_data.get(field):
                raise ValueError(f"Missing required field: {field}")
        
        response = supabase_admin.table('clients').insert(client_data).execute()
        return response.data[0] if response.data else None
            
    except Exception as e:
        print(f"❌ ERROR: Failed to create client: {e}")
        return None

def update_client_in_db(client_id, client_data):
    """Update an existing client"""
    try:
        response = supabase_admin.table('clients').update(client_data).eq('id', client_id).execute()
        return response.data[0] if response.data else {'success': True}
    except Exception as e:
        print(f"❌ ERROR: Failed to update client: {e}")
        return None

def delete_client_from_db(client_id):
    """Delete a client"""
    try:
        # Check for existing bookings
        bookings_check = supabase_admin.table('bookings').select('id').eq('client_id', client_id).execute()
        
        if bookings_check.data:
            return False, "Cannot delete client with existing bookings"
        
        # Delete client
        supabase_admin.table('clients').delete().eq('id', client_id).execute()
        return True, "Client deleted successfully"
        
    except Exception as e:
        print(f"❌ ERROR: Failed to delete client: {e}")
        return False, f"Error deleting client: {str(e)}"

def get_clients_with_booking_counts():
    """Get all clients with their booking counts"""
    try:
        # Fetch all clients
        clients = get_all_clients_from_db()
        
        # Fetch booking counts
        bookings_response = supabase_admin.table('bookings').select('id, client_id').execute()
        bookings = bookings_response.data if bookings_response.data else []
        
        # Count bookings per client
        booking_counts = {}
        for booking in bookings:
            client_id = booking.get('client_id')
            if client_id:
                booking_counts[client_id] = booking_counts.get(client_id, 0) + 1
        
        # Add counts to clients
        for client in clients:
            client['booking_count'] = booking_counts.get(client['id'], 0)
            client['display_name'] = client.get('company_name') or client.get('contact_person', 'Unknown')
        
        return clients
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get clients with booking counts: {e}")
        return []

def find_or_create_client_enhanced(client_name, company_name=None, email=None, phone=None):
    """Find existing client or create new one"""
    try:
        if not client_name or not client_name.strip():
            return None
        
        client_name = client_name.strip()
        company_name = company_name.strip() if company_name else None
        email = email.strip().lower() if email else None
        phone = phone.strip() if phone else None
        
        # Search for existing client
        existing_client = None
        clients = get_all_clients_from_db()
        
        for client in clients:
            # Check by company name
            if company_name and client.get('company_name'):
                if client['company_name'].strip().lower() == company_name.lower():
                    existing_client = client
                    break
            
            # Check by contact person
            if client.get('contact_person'):
                if client['contact_person'].strip().lower() == client_name.lower():
                    existing_client = client
                    break
            
            # Check by email
            if email and client.get('email'):
                if client['email'].strip().lower() == email:
                    existing_client = client
                    break
            
            # Check by phone
            if phone and client.get('phone'):
                if client['phone'].strip() == phone:
                    existing_client = client
                    break
        
        if existing_client:
            return existing_client['id']
        
        # Create new client
        client_data = {
            'contact_person': client_name,
            'company_name': company_name,
            'email': email or f"{client_name.lower().replace(' ', '.')}@example.com",
            'phone': phone,
            'created_at': datetime.now(UTC).isoformat(),
            'notes': f'Auto-created from booking form'
        }
        
        result = create_client_in_db(client_data)
        return result['id'] if result else None
            
    except Exception as e:
        print(f"❌ ERROR: Failed to find/create client: {e}")
        return None

# ===============================
# ROOM MANAGEMENT
# ===============================

def is_room_available_supabase(room_id, start_time, end_time, exclude_booking_id=None):
    """Check if a room is available for given time period"""
    try:
        query = supabase_admin.table('bookings').select('id')
        query = query.eq('room_id', room_id)
        query = query.neq('status', 'cancelled')
        query = query.lt('start_time', end_time.isoformat())
        query = query.gt('end_time', start_time.isoformat())
        
        if exclude_booking_id:
            query = query.neq('id', exclude_booking_id)
        
        response = query.execute()
        return len(response.data) == 0
    except Exception as e:
        print(f"Availability check error: {e}")
        return False

def check_room_conflicts(room_id, start_time, end_time, exclude_booking_id=None):
    """Get all conflicting bookings for a room and time period"""
    try:
        query = supabase_admin.table('bookings').select('id, title, status, start_time, end_time')
        query = query.eq('room_id', room_id)
        query = query.neq('status', 'cancelled')
        query = query.lt('start_time', end_time.isoformat())
        query = query.gt('end_time', start_time.isoformat())
        
        if exclude_booking_id:
            query = query.neq('id', exclude_booking_id)
        
        response = query.execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Conflict check error: {e}")
        return []

# ===============================
# BOOKING MANAGEMENT
# ===============================

def extract_booking_form_data(form_data, is_update=False):
    """Extract and validate booking data from form submission"""
    try:
        print(f"🔍 Extracting form data (is_update: {is_update})")
        print(f"🔍 Available form fields: {list(form_data.keys())}")
        
        # Required fields validation
        required_fields = {
            'room_id': 'Please select a venue',
            'attendees': 'Please enter number of attendees',
            'client_name': 'Please enter client name',
            'event_type': 'Please select event type',
            'start_time': 'Please select start date and time',
            'end_time': 'Please select end date and time'
        }
        
        for field, message in required_fields.items():
            value = form_data.get(field, '').strip()
            print(f"🔍 Field {field}: '{value}'")
            if not value:
                print(f"❌ Missing required field: {field}")
                flash(f'❌ {message}', 'danger')
                return None
        
        # Parse datetime fields
        try:
            start_time_str = form_data.get('start_time')
            end_time_str = form_data.get('end_time')
            print(f"🔍 Parsing datetime - start: '{start_time_str}', end: '{end_time_str}'")
            
            start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M')
            end_time = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M')
            print(f"✅ Datetime parsing successful")
        except ValueError as e:
            print(f"❌ Datetime parsing error: {e}")
            flash('❌ Invalid date/time format', 'danger')
            return None
        
        # Validate time logic
        if end_time <= start_time:
            print(f"❌ Time validation error: end_time <= start_time")
            flash('❌ End time must be after start time', 'danger')
            return None
        
        # Only check past time for new bookings, not updates
        if not is_update and start_time < datetime.now():
            print(f"❌ Past time validation error for new booking")
            flash('❌ Booking cannot be scheduled in the past', 'danger')
            return None
        elif is_update and start_time < datetime.now():
            print(f"⚠️ Updating booking with past start time (allowed for updates)")
        
        print(f"✅ All validations passed")
        
        # Process pricing items
        pricing_items, total_price = extract_pricing_items_from_form(form_data)
        
        # If no pricing items, calculate basic room rate
        if not pricing_items or total_price <= 0:
            room_id = int(form_data.get('room_id'))
            total_price = calculate_booking_total(room_id, start_time, end_time)
            
            # Create basic pricing item
            room_data = supabase_select('rooms', filters=[('id', 'eq', room_id)])
            room_name = room_data[0].get('name', 'Conference Room') if room_data else 'Conference Room'
            
            duration_hours = (end_time - start_time).total_seconds() / 3600
            pricing_items = [{
                'description': f'{room_name} Rental',
                'quantity': 1,
                'unit_price': total_price,
                'total_price': total_price,
                'notes': f'Duration: {duration_hours:.1f} hours'
            }]
        
        # Build booking data
        booking_data = {
            'room_id': int(form_data.get('room_id')),
            'attendees': int(form_data.get('attendees')),
            'client_name': form_data.get('client_name', '').strip(),
            'company_name': form_data.get('company_name', '').strip() or None,
            'client_email': form_data.get('client_email', '').strip() or None,
            'event_type': form_data.get('event_type', '').strip(),
            'custom_event_type': form_data.get('custom_event_type', '').strip() or None,
            'start_time': start_time,
            'end_time': end_time,
            'notes': form_data.get('notes', '').strip() or None,
            'status': form_data.get('status', 'tentative'),
            'pricing_items': pricing_items,
            'total_price': total_price
        }
        
        return booking_data
        
    except Exception as e:
        print(f"❌ ERROR: Failed to extract form data: {e}")
        flash('❌ Error processing form data', 'danger')
        return None

def extract_pricing_items_from_form(form_data):
    """Extract pricing items from dynamic form fields"""
    try:
        pricing_items = []
        total_price = 0
        
        item_index = 0
        while f'pricing_items[{item_index}][description]' in form_data:
            description = form_data.get(f'pricing_items[{item_index}][description]', '').strip()
            quantity_str = form_data.get(f'pricing_items[{item_index}][quantity]', '1')
            price_str = form_data.get(f'pricing_items[{item_index}][price]', '0')
            notes = form_data.get(f'pricing_items[{item_index}][notes]', '').strip()
            
            try:
                quantity = int(quantity_str) if quantity_str else 1
                price = float(price_str) if price_str else 0.0
            except (ValueError, TypeError):
                item_index += 1
                continue
            
            if description and price > 0 and quantity > 0:
                item_total = quantity * price
                total_price += item_total
                
                pricing_items.append({
                    'description': description,
                    'quantity': quantity,
                    'unit_price': price,
                    'total_price': item_total,
                    'notes': notes if notes else None
                })
            
            item_index += 1
        
        return pricing_items, total_price
        
    except Exception as e:
        print(f"❌ ERROR: Failed to extract pricing items: {e}")
        return [], 0

def calculate_booking_total(room_id, start_time, end_time, addon_ids=None):
    """Calculate total price for a booking"""
    try:
        # Get room data
        room_data = supabase_select('rooms', filters=[('id', 'eq', room_id)])
        if not room_data:
            return 0
        
        room = room_data[0]
        
        # Calculate duration in hours
        duration_hours = (end_time - start_time).total_seconds() / 3600
        
        # Calculate room rate based on duration
        if duration_hours <= 4:
            room_rate = float(room['hourly_rate']) * duration_hours
        elif duration_hours <= 6:
            room_rate = float(room['half_day_rate'])
        else:
            room_rate = float(room['full_day_rate'])
        
        # Calculate add-ons total
        addons_total = 0
        if addon_ids:
            for addon_id in addon_ids:
                addon_data = supabase_select('addons', filters=[('id', 'eq', addon_id)])
                if addon_data:
                    addons_total += float(addon_data[0]['price'])
        
        total = room_rate + addons_total
        return max(total, 0)
        
    except Exception as e:
        print(f"Price calculation error: {e}")
        return 0

def validate_booking_business_rules(booking_data, exclude_booking_id=None):
    """Validate booking against business rules"""
    errors = []
    warnings = []
    
    try:
        # Check room availability - Only block if there's a CONFIRMED booking
        conflicting_bookings = check_room_conflicts(
            booking_data['room_id'],
            booking_data['start_time'],
            booking_data['end_time'],
            exclude_booking_id=exclude_booking_id
        )
        
        # Only error if there are confirmed conflicts
        confirmed_conflicts = [b for b in conflicting_bookings if b.get('status') == 'confirmed']
        if confirmed_conflicts:
            conflict_details = []
            for conflict in confirmed_conflicts:
                start_time_str = conflict.get('start_time', 'Unknown time')
                title = conflict.get('title', 'Untitled event')
                
                # Format the time better
                try:
                    if start_time_str and start_time_str != 'Unknown time':
                        # Parse the ISO datetime string
                        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                        formatted_time = start_time.strftime('%Y-%m-%d %H:%M')
                        conflict_details.append(f"'{title}' on {formatted_time}")
                    else:
                        conflict_details.append(f"'{title}' (time unknown)")
                except Exception:
                    conflict_details.append(f"'{title}' at {start_time_str}")
            
            error_msg = f'❌ Room is not available - confirmed booking(s) exist: {", ".join(conflict_details)}'
            errors.append(error_msg)
        
        # Warn about tentative conflicts
        tentative_conflicts = [b for b in conflicting_bookings if b.get('status') == 'tentative']
        if tentative_conflicts:
            conflict_details = []
            for conflict in tentative_conflicts:
                start_time_str = conflict.get('start_time', 'Unknown time')
                title = conflict.get('title', 'Untitled event')
                
                # Format the time better
                try:
                    if start_time_str and start_time_str != 'Unknown time':
                        # Parse the ISO datetime string
                        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                        formatted_time = start_time.strftime('%Y-%m-%d %H:%M')
                        conflict_details.append(f"'{title}' on {formatted_time}")
                    else:
                        conflict_details.append(f"'{title}' (time unknown)")
                except Exception:
                    conflict_details.append(f"'{title}' at {start_time_str}")
            
            warning_msg = f'⚠️ Warning: Room has tentative booking(s) that may conflict: {", ".join(conflict_details)}'
            warnings.append(warning_msg)
            # Store the warning in session so it can be displayed to user (only if in request context)
            try:
                from flask import session
                if 'booking_warnings' not in session:
                    session['booking_warnings'] = []
                session['booking_warnings'].append(warning_msg)
            except RuntimeError:
                # Not in request context, skip session storage
                pass
        
        # Check room capacity - Allow over capacity but give warning
        room_data = supabase_select('rooms', filters=[('id', 'eq', booking_data['room_id'])])
        if room_data:
            room_capacity = room_data[0].get('capacity', 0)
            if booking_data['attendees'] > room_capacity:
                # Changed from error to warning - allow the booking to proceed
                warnings.append(f'⚠️ Warning: Attendees ({booking_data["attendees"]}) exceed room capacity ({room_capacity})')
                # Store the warning in session so it can be displayed to user (only if in request context)
                try:
                    from flask import session
                    if 'booking_warnings' not in session:
                        session['booking_warnings'] = []
                    session['booking_warnings'].append(f'Room capacity exceeded: {booking_data["attendees"]} attendees in room with capacity {room_capacity}')
                except RuntimeError:
                    # Not in request context, skip session storage
                    pass
        
        # Validate booking duration with multi-day support
        duration = booking_data['end_time'] - booking_data['start_time']
        duration_days = duration.days
        duration_hours = duration.total_seconds() / 3600
        
        # Allow multi-day bookings (up to 30 days for conferences/events)
        if duration_days > 30:
            errors.append('❌ Bookings cannot exceed 30 days')
        
        if duration_hours < 0.5:
            errors.append('❌ Bookings must be at least 30 minutes long')
        
        # For single day bookings, validate business hours
        if duration_days == 0:
            if booking_data['start_time'].hour < 6 or booking_data['start_time'].hour > 22:
                errors.append('❌ Same-day bookings must start within business hours (6 AM - 10 PM)')
            
            if booking_data['end_time'].hour < 6 or booking_data['end_time'].hour > 23:
                errors.append('❌ Same-day bookings must end within business hours (6 AM - 11 PM)')
            
            # Remove 12-hour limit to allow all-day events
            if duration_hours > 24:
                errors.append('❌ Single-day bookings cannot exceed 24 hours')
        
    except Exception as e:
        print(f"❌ ERROR: Business rule validation failed: {e}")
        errors.append('❌ Error validating booking rules')
    
    return {'errors': errors, 'warnings': warnings}

def find_or_create_event_type(event_type, custom_event_type=None):
    """Find or create event type"""
    try:
        # Determine event type name
        if event_type == 'other' and custom_event_type:
            event_name = custom_event_type.strip()
        else:
            event_name = event_type.replace('_', ' ').title()
        
        # Search for existing
        existing_event = supabase_admin.table('event_types').select('*').eq('name', event_name).execute()
        
        if existing_event.data:
            event_type_id = existing_event.data[0]['id']
            # Increment usage count
            supabase_admin.table('event_types').update({
                'usage_count': existing_event.data[0]['usage_count'] + 1
            }).eq('id', event_type_id).execute()
            return event_type_id
        
        # Create new
        event_data = {
            'name': event_name,
            'usage_count': 1,
            'created_at': datetime.now(UTC).isoformat()
        }
        
        result = supabase_insert('event_types', event_data)
        return result['id'] if result else None
            
    except Exception as e:
        print(f"❌ ERROR: Failed to find/create event type: {e}")
        return None

def create_complete_booking(booking_data, client_id, event_type_id):
    """Create booking with all related data"""
    try:
        # Determine event title
        if booking_data['event_type'] == 'other' and booking_data['custom_event_type']:
            event_title = booking_data['custom_event_type']
        else:
            event_title = booking_data['event_type'].replace('_', ' ').title()
        
        # Calculate room rate and addons
        room_rate, addons_total = calculate_room_and_addons_totals(booking_data['pricing_items'])
        
        # Create booking record
        booking_record = {
            'room_id': booking_data['room_id'],
            'client_id': client_id,
            'event_type_id': event_type_id,
            'title': f"{event_title} - {booking_data['client_name']}",
            'start_time': booking_data['start_time'].isoformat(),
            'end_time': booking_data['end_time'].isoformat(),
            'attendees': booking_data['attendees'],
            'status': booking_data['status'],
            'notes': booking_data['notes'],
            'room_rate': room_rate,
            'addons_total': addons_total,
            'total_price': booking_data['total_price'],
            'created_by': current_user.id,
            'created_at': datetime.now(UTC).isoformat(),
            'client_name': booking_data['client_name'],
            'company_name': booking_data['company_name'],
            'client_email': booking_data['client_email']
        }
        
        booking_result = supabase_insert('bookings', booking_record)
        if not booking_result:
            return None
        
        booking_id = booking_result['id']
        
        # Create custom addon records
        for item in booking_data['pricing_items']:
            addon_record = {
                'booking_id': booking_id,
                'description': item['description'],
                'quantity': item['quantity'],
                'unit_price': item['unit_price'],
                'total_price': item['total_price'],
                'notes': item.get('notes'),
                'created_at': datetime.now(UTC).isoformat()
            }
            
            supabase_insert('booking_custom_addons', addon_record)
        
        # Send confirmation email for confirmed bookings
        if booking_data['status'] == 'confirmed':
            try:
                # Get complete booking details for email
                booking_details = get_booking_details_for_email(booking_id, booking_data)
                send_booking_confirmation_email(booking_details)
                print(f"✅ Confirmation email sent for booking #{booking_id}")
            except Exception as email_error:
                print(f"⚠️ WARNING: Failed to send confirmation email for booking #{booking_id}: {email_error}")
                # Don't fail the booking creation if email fails
        
        # Log booking creation in audit trail
        try:
            room_name = get_room_name_by_id(booking_data['room_id'])
            log_booking_change(
                booking_id=booking_id,
                action_type='created',
                change_summary=f"Created new booking for {booking_data['client_name']} in {room_name} from {booking_data['start_time'].strftime('%Y-%m-%d %H:%M')} to {booking_data['end_time'].strftime('%Y-%m-%d %H:%M')}"
            )
        except Exception as audit_error:
            print(f"⚠️ WARNING: Failed to log booking creation audit: {audit_error}")
        
        return booking_id
        
    except Exception as e:
        print(f"❌ ERROR: Failed to create booking: {e}")
        return None

def get_complete_booking_details(booking_id):
    """Get complete booking details including all related data"""
    try:
        # Get booking with relations
        booking_response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(*),
            client:clients(*),
            event_type:event_types(*)
        """).eq('id', booking_id).execute()
        
        if not booking_response.data:
            return None
        
        booking = booking_response.data[0]
        
        # Get custom addons
        addons_response = supabase_admin.table('booking_custom_addons').select('*').eq('booking_id', booking_id).execute()
        booking['custom_addons'] = addons_response.data if addons_response.data else []
        
        # Convert datetime strings
        booking = convert_datetime_strings(booking)
        
        return booking
        
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch booking details: {e}")
        return None

def update_complete_booking(booking_id, booking_data, existing_booking):
    """Update booking with all related data and log changes"""
    try:
        # Compare old and new data to track changes
        changes = compare_booking_data(existing_booking, booking_data)
        
        # Find or create client if changed
        client_id = existing_booking.get('client_id')
        if (booking_data['client_name'] != existing_booking.get('client', {}).get('contact_person', '') or
            booking_data.get('company_name') != existing_booking.get('client', {}).get('company_name')):
            
            client_id = find_or_create_client_enhanced(
                booking_data['client_name'],
                booking_data.get('company_name'),
                booking_data.get('client_email')
            )
        
        # Find or create event type if changed
        event_type_id = existing_booking.get('event_type_id')
        if booking_data['event_type'] != existing_booking.get('event_type'):
            event_type_id = find_or_create_event_type(
                booking_data['event_type'],
                booking_data.get('custom_event_type')
            )
        
        # Determine event title
        if booking_data['event_type'] == 'other' and booking_data['custom_event_type']:
            event_title = booking_data['custom_event_type']
        else:
            event_title = booking_data['event_type'].replace('_', ' ').title()
        
        # Calculate room rate and addons
        room_rate, addons_total = calculate_room_and_addons_totals(booking_data['pricing_items'])
        
        # Update booking record
        booking_update = {
            'room_id': booking_data['room_id'],
            'client_id': client_id,
            'event_type_id': event_type_id,
            'title': f"{event_title} - {booking_data['client_name']}",
            'start_time': booking_data['start_time'].isoformat(),
            'end_time': booking_data['end_time'].isoformat(),
            'attendees': booking_data['attendees'],
            'status': booking_data['status'],
            'notes': booking_data['notes'],
            'room_rate': room_rate,
            'addons_total': addons_total,
            'total_price': booking_data['total_price'],
            'updated_at': datetime.now(UTC).isoformat(),
            'client_name': booking_data['client_name'],
            'company_name': booking_data['company_name'],
            'client_email': booking_data['client_email']
        }
        
        booking_result = supabase_update('bookings', booking_update, [('id', 'eq', booking_id)])
        if not booking_result:
            return False
        
        # Delete existing custom addons
        supabase_admin.table('booking_custom_addons').delete().eq('booking_id', booking_id).execute()
        
        # Create new custom addon records
        for item in booking_data['pricing_items']:
            addon_record = {
                'booking_id': booking_id,
                'description': item['description'],
                'quantity': item['quantity'],
                'unit_price': item['unit_price'],
                'total_price': item['total_price'],
                'notes': item.get('notes'),
                'created_at': datetime.now(UTC).isoformat()
            }
            
            supabase_insert('booking_custom_addons', addon_record)
        
        # Log audit trail for each change
        if changes:
            for change in changes:
                # Log specific field changes
                log_booking_change(
                    booking_id=booking_id,
                    action_type='updated',
                    field_changed=change['field'],
                    old_value=change['old_value'],
                    new_value=change['new_value'],
                    change_summary=f"Changed {change['field_display']} from '{change['old_value']}' to '{change['new_value']}'"
                )
            
            # Log general update action
            change_summary = f"Updated booking with {len(changes)} change{'s' if len(changes) != 1 else ''}: " + \
                           ", ".join([change['field_display'] for change in changes])
            log_booking_change(
                booking_id=booking_id,
                action_type='updated',
                change_summary=change_summary
            )
        else:
            # No changes detected, but still log the update attempt
            log_booking_change(
                booking_id=booking_id,
                action_type='updated',
                change_summary="Booking update attempted with no changes"
            )
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: Failed to update booking: {e}")
        return False

def calculate_room_and_addons_totals(pricing_items):
    """Calculate separate room rate and addons total from pricing items"""
    try:
        room_rate = 0.0
        addons_total = 0.0
        
        # Keywords that typically indicate room/venue charges
        room_keywords = ['room', 'venue', 'hall', 'space', 'rental', 'hire', 'facility']
        
        for item in pricing_items:
            description = item['description'].lower()
            item_total = item['total_price']
            
            # Check if this item is likely a room charge
            is_room_item = any(keyword in description for keyword in room_keywords)
            
            if is_room_item:
                room_rate += item_total
                item['is_room_rate'] = True
            else:
                addons_total += item_total
                item['is_room_rate'] = False
        
        # If no room items identified, treat first item as room rate
        if room_rate == 0 and pricing_items:
            first_item = pricing_items[0]
            room_rate = first_item['total_price']
            addons_total = sum(item['total_price'] for item in pricing_items[1:])
            first_item['is_room_rate'] = True
            for item in pricing_items[1:]:
                item['is_room_rate'] = False
        
        return room_rate, addons_total
        
    except Exception as e:
        print(f"❌ ERROR: Failed to calculate totals: {e}")
        return 0.0, 0.0

def calculate_booking_totals(booking, room_rates=None):
    """Calculate booking totals"""
    try:
        # Parse times safely
        if isinstance(booking.get('start_time'), str):
            start_time = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00')).replace(tzinfo=None)
            end_time = datetime.fromisoformat(booking['end_time'].replace('Z', '+00:00')).replace(tzinfo=None)
        else:
            start_time = booking.get('start_time')
            end_time = booking.get('end_time')
        
        if not start_time or not end_time:
            # Fallback values
            duration_hours = 4
            room_rate = safe_float_conversion(booking.get('total_price', 0)) * 0.7
            rate_type = "Estimated Rate"
        else:
            duration_hours = (end_time - start_time).total_seconds() / 3600
            
            # Get room rates
            if room_rates:
                hourly_rate = safe_float_conversion(room_rates.get('hourly_rate', 0))
                half_day_rate = safe_float_conversion(room_rates.get('half_day_rate', 0))
                full_day_rate = safe_float_conversion(room_rates.get('full_day_rate', 0))
            else:
                room = booking.get('room', {})
                hourly_rate = safe_float_conversion(room.get('hourly_rate', 50))
                half_day_rate = safe_float_conversion(room.get('half_day_rate', 200))
                full_day_rate = safe_float_conversion(room.get('full_day_rate', 350))
            
            # Calculate room rate based on duration
            if duration_hours <= 4:
                room_rate = hourly_rate * duration_hours
                rate_type = f"Hourly Rate ({duration_hours:.1f} hours)"
            elif duration_hours <= 6:
                room_rate = half_day_rate
                rate_type = "Half-day Rate"
            else:
                room_rate = full_day_rate
                rate_type = "Full-day Rate"
        
        # Calculate addons total
        addons_total = 0
        addon_items = []
        
        # Check custom addons
        for addon in booking.get('custom_addons', []):
            addons_total += safe_float_conversion(addon.get('total_price', 0))
            addon_items.append({
                'name': addon.get('description', 'Unknown Item'),
                'quantity': addon.get('quantity', 1),
                'price': safe_float_conversion(addon.get('unit_price', 0)),
                'total': safe_float_conversion(addon.get('total_price', 0))
            })
        
        # Use stored values if custom addons not available
        if not addon_items and booking.get('addons_total'):
            addons_total = safe_float_conversion(booking.get('addons_total', 0))
        
        # Use stored room rate if available
        if booking.get('room_rate'):
            room_rate = safe_float_conversion(booking.get('room_rate', room_rate))
        
        total = room_rate + addons_total
        
        return {
            'room_rate': round(room_rate, 2),
            'rate_type': rate_type,
            'addons_total': round(addons_total, 2),
            'addon_items': addon_items,
            'duration_hours': round(duration_hours, 1),
            'subtotal': round(total, 2),
            'total': round(total, 2)
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to calculate booking totals: {e}")
        total_price = safe_float_conversion(booking.get('total_price', 100))
        return {
            'room_rate': round(total_price * 0.7, 2),
            'rate_type': 'Estimated Rate',
            'addons_total': round(total_price * 0.3, 2),
            'addon_items': [],
            'duration_hours': 4,
            'subtotal': round(total_price, 2),
            'total': round(total_price, 2)
        }

def get_booking_calendar_events_supabase():
    """Get all bookings formatted for calendar display with enhanced error handling"""
    try:
        # Get all bookings with related data
        bookings_response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity),
            client:clients(id, contact_person, company_name, email, phone)
        """).neq('status', 'cancelled').execute()
        
        if not bookings_response.data:
            return []
        
        events = []
        for booking in bookings_response.data:
            try:
                # Get room name with fallbacks
                room_name = 'Room Details Loading...'
                room_id = booking.get('room_id')
                
                if booking.get('room') and isinstance(booking['room'], dict):
                    room_name = (booking['room'].get('name') or '').strip()
                    if not room_name:
                        room_name = f"Room {room_id}" if room_id else 'Room Details Loading...'
                elif booking.get('room_name'):
                    room_name = (booking.get('room_name') or '').strip()
                    if not room_name:
                        room_name = f"Room {room_id}" if room_id else 'Room Details Loading...'
                
                # Get client name with fallbacks
                client_name = 'Client Details Loading...'
                client_id = booking.get('client_id')
                
                if booking.get('client') and isinstance(booking['client'], dict):
                    client = booking['client']
                    company_name = (client.get('company_name') or '').strip()
                    contact_person = (client.get('contact_person') or '').strip()
                    
                    if company_name:
                        client_name = company_name
                    elif contact_person:
                        client_name = contact_person
                    else:
                        client_name = f"Client {client_id}" if client_id else 'Client Details Loading...'
                elif booking.get('client_name'):
                    client_name = (booking.get('client_name') or '').strip()
                    if not client_name:
                        client_name = f"Client {client_id}" if client_id else 'Client Details Loading...'
                
                # Determine event color based on status
                status = booking.get('status', 'tentative')
                color_map = {
                    'tentative': '#FFA500',    # Orange
                    'confirmed': '#28a745',    # Green
                    'cancelled': '#dc3545',    # Red
                    'completed': '#17a2b8'     # Teal
                }
                color = color_map.get(status, '#6c757d')  # Default: Gray
                
                # Create meaningful title
                event_title = booking.get('title', '').strip()
                if not event_title:
                    event_type = booking.get('event_type', 'Conference').replace('_', ' ').title()
                    if event_type == 'Other' and booking.get('custom_event_type'):
                        event_type = booking.get('custom_event_type').strip()
                    event_title = f"{event_type} - {client_name}"
                
                # Calculate duration for display
                duration_display = 'Duration TBD'
                try:
                    if booking.get('start_time') and booking.get('end_time'):
                        start_time = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
                        end_time = datetime.fromisoformat(booking['end_time'].replace('Z', '+00:00'))
                        duration = end_time - start_time
                        
                        if duration.days > 0:
                            duration_display = f"{duration.days}d {duration.seconds//3600}h"
                        else:
                            hours = duration.seconds // 3600
                            minutes = (duration.seconds % 3600) // 60
                            if hours > 0:
                                duration_display = f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
                            else:
                                duration_display = f"{minutes}m"
                except Exception:
                    pass
                
                # Create event with comprehensive data
                event_data = {
                    'id': booking['id'],
                    'title': event_title,
                    'start': booking.get('start_time'),
                    'end': booking.get('end_time'),
                    'color': color,
                    'borderColor': color,
                    'textColor': '#ffffff',
                    'extendedProps': {
                        'room': room_name,
                        'roomId': room_id,
                        'client': client_name,
                        'clientId': client_id,
                        'attendees': booking.get('attendees', 0),
                        'total': safe_float_conversion(booking.get('total_price', 0)),
                        'status': status.replace('_', ' ').title(),
                        'statusRaw': status,
                        'notes': booking.get('notes', ''),
                        'duration': duration_display,
                        'event_type': booking.get('event_type', 'conference'),
                        'description': f"{room_name} • {client_name} • {booking.get('attendees', 0)} attendees"
                    }
                }
                
                events.append(event_data)
                
            except Exception as e:
                print(f"⚠️ Error processing booking {booking.get('id')} for calendar: {e}")
                # Create minimal event for problematic bookings
                events.append({
                    'id': booking.get('id', 'unknown'),
                    'title': f"Booking {booking.get('id', 'Unknown')} - Data Loading...",
                    'start': booking.get('start_time'),
                    'end': booking.get('end_time'),
                    'color': '#6c757d',
                    'extendedProps': {
                        'room': 'Room Details Loading...',
                        'client': 'Client Details Loading...',
                        'status': 'Loading...',
                        'attendees': 0,
                        'total': 0
                    }
                })
        
        print(f"✅ Generated {len(events)} calendar events")
        return events
        
    except Exception as e:
        print(f"❌ Calendar events error: {e}")
        import traceback
        traceback.print_exc()
        return []

def format_booking_success_message(booking_data):
    """Format a success message for booking creation"""
    event_title = booking_data.get('custom_event_type') if booking_data.get('event_type') == 'other' else booking_data.get('event_type', 'Event').replace('_', ' ').title()
    
    return f"""
    ✅ <strong>Booking created successfully!</strong><br>
    📋 <strong>Event:</strong> {event_title}<br>
    👤 <strong>Client:</strong> {booking_data.get('client_name')}<br>
    🏢 <strong>Company:</strong> {booking_data.get('company_name') or 'Not specified'}<br>
    👥 <strong>Attendees:</strong> {booking_data.get('attendees')}<br>
    💰 <strong>Total:</strong> ${booking_data.get('total_price'):.2f}
    """

# ===============================
# HANDLER FUNCTIONS
# ===============================

def handle_booking_creation(form_data, rooms_for_template):
    """Handle the creation of a new booking"""
    try:
        from flask import render_template
        
        # Extract and validate form data
        booking_data = extract_booking_form_data(form_data)
        if not booking_data:
            return render_template('bookings/form.html', 
                                  title='New Booking', 
                                  form=BookingForm(), 
                                  rooms=rooms_for_template)
        
        # Validate business rules
        validation_result = validate_booking_business_rules(booking_data)
        validation_errors = validation_result.get('errors', [])
        validation_warnings = validation_result.get('warnings', [])
        
        if validation_errors:
            for error in validation_errors:
                flash(error, 'danger')
            return render_template('bookings/form.html', 
                                  title='New Booking', 
                                  form=BookingForm(), 
                                  rooms=rooms_for_template)
        
        # Show warnings if any
        for warning in validation_warnings:
            flash(warning, 'warning')
        
        # Find or create client
        client_id = find_or_create_client_enhanced(
            booking_data['client_name'], 
            booking_data.get('company_name'),
            booking_data.get('client_email')
        )
        
        if not client_id:
            flash('❌ Error processing client information', 'danger')
            return render_template('bookings/form.html', 
                                  title='New Booking', 
                                  form=BookingForm(), 
                                  rooms=rooms_for_template)
        
        # Find or create event type
        event_type_id = find_or_create_event_type(
            booking_data['event_type'], 
            booking_data.get('custom_event_type')
        )
        
        # Create booking
        booking_id = create_complete_booking(booking_data, client_id, event_type_id)
        
        if booking_id:
            safe_log_user_activity(
                ActivityTypes.CREATE_BOOKING,
                f"Created booking for {booking_data.get('client_name')}",
                resource_type='booking',
                resource_id=booking_id
            )
            
            success_message = format_booking_success_message(booking_data)
            flash(success_message, 'success')
            
            return redirect(url_for('bookings.view_booking', id=booking_id))
        else:
            flash('❌ Error creating booking', 'danger')
            return render_template('bookings/form.html', 
                                  title='New Booking', 
                                  form=BookingForm(), 
                                  rooms=rooms_for_template)
        
    except Exception as e:
        print(f"❌ ERROR: Booking creation failed: {e}")
        flash('❌ Unexpected error creating booking', 'danger')
        return render_template('bookings/form.html', 
                              title='New Booking', 
                              form=BookingForm(), 
                              rooms=rooms_for_template)

def handle_booking_update(booking_id, form_data, existing_booking, rooms_for_template):
    """Handle updating an existing booking"""
    try:
        from flask import render_template
        
        print(f"🔍 Starting booking update for ID: {booking_id}")
        print(f"🔍 Form data keys: {list(form_data.keys())}")
        
        # Extract and validate form data
        booking_data = extract_booking_form_data(form_data, is_update=True)
        if not booking_data:
            print("❌ Failed to extract booking data")
            return render_template('bookings/form.html', 
                                  title='Edit Booking', 
                                  form=BookingForm(), 
                                  booking=existing_booking,
                                  rooms=rooms_for_template)
        
        print(f"✅ Booking data extracted successfully")
        
        # Validate business rules
        validation_result = validate_booking_business_rules(booking_data, exclude_booking_id=booking_id)
        validation_errors = validation_result.get('errors', [])
        validation_warnings = validation_result.get('warnings', [])
        
        if validation_errors:
            print(f"❌ Validation errors: {validation_errors}")
            for error in validation_errors:
                flash(error, 'danger')
            return render_template('bookings/form.html', 
                                  title='Edit Booking', 
                                  form=BookingForm(), 
                                  booking=existing_booking,
                                  rooms=rooms_for_template)
        
        # Show warnings if any
        for warning in validation_warnings:
            flash(warning, 'warning')
        
        print(f"✅ Business rules validation passed")
        
        # Update booking
        success = update_complete_booking(booking_id, booking_data, existing_booking)
        
        if success:
            print(f"✅ Booking updated successfully")
            safe_log_user_activity(
                ActivityTypes.UPDATE_BOOKING,
                f"Updated booking for {booking_data.get('client_name')}",
                resource_type='booking',
                resource_id=booking_id
            )
            
            flash('✅ Booking updated successfully!', 'success')
            return redirect(url_for('bookings.view_booking', id=booking_id))
        else:
            print(f"❌ Failed to update booking in database")
            flash('❌ Error updating booking', 'danger')
            return render_template('bookings/form.html', 
                                  title='Edit Booking', 
                                  form=BookingForm(), 
                                  booking=existing_booking,
                                  rooms=rooms_for_template)
        
    except Exception as e:
        print(f"❌ ERROR: Booking update failed: {e}")
        flash('❌ Unexpected error updating booking', 'danger')
        return render_template('bookings/form.html', 
                              title='Edit Booking', 
                              form=BookingForm(), 
                              booking=existing_booking,
                              rooms=rooms_for_template)

# ===============================
# ACTIVITY TYPE CONSTANTS
# ===============================

class ActivityTypes:
    # Authentication
    LOGIN_SUCCESS = 'login_success'
    LOGIN_FAILED = 'login_failed'
    LOGOUT = 'logout'
    REGISTRATION = 'registration'
    
    # Bookings
    CREATE_BOOKING = 'create_booking'
    UPDATE_BOOKING = 'update_booking'
    DELETE_BOOKING = 'delete_booking'
    CANCEL_BOOKING = 'cancel_booking'
    CHANGE_BOOKING_STATUS = 'change_booking_status'
    VIEW_BOOKING = 'view_booking'
    
    # Rooms
    CREATE_ROOM = 'create_room'
    UPDATE_ROOM = 'update_room'
    DELETE_ROOM = 'delete_room'
    VIEW_ROOM = 'view_room'
    
    # Clients
    CREATE_CLIENT = 'create_client'
    UPDATE_CLIENT = 'update_client'
    DELETE_CLIENT = 'delete_client'
    VIEW_CLIENT = 'view_client'
    
    # Add-ons
    CREATE_ADDON = 'create_addon'
    UPDATE_ADDON = 'update_addon'
    DELETE_ADDON = 'delete_addon'
    CREATE_ADDON_CATEGORY = 'create_addon_category'
    
    # Reports
    GENERATE_REPORT = 'generate_report'
    EXPORT_DATA = 'export_data'
    
    # System
    PAGE_VIEW = 'page_view'
    API_CALL = 'api_call'
    ERROR_OCCURRED = 'error_occurred'

# ===============================
# FORMS
# ===============================

from wtforms import StringField, PasswordField, BooleanField, SelectField, DateTimeField, TextAreaField, IntegerField, DecimalField, HiddenField
from flask_wtf import FlaskForm
from wtforms.validators import DataRequired, Email, Length, ValidationError, EqualTo

class ClientForm(FlaskForm):
    company_name = StringField('Company Name')
    contact_person = StringField('Contact Person', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number')
    address = TextAreaField('Address')
    notes = TextAreaField('Notes')

class RoomForm(FlaskForm):
    name = StringField('Room Name', validators=[DataRequired()])
    capacity = IntegerField('Capacity')
    description = TextAreaField('Description')
    hourly_rate = DecimalField('Hourly Rate (USD)', places=2)
    half_day_rate = DecimalField('Half-Day Rate (USD)', places=2)
    full_day_rate = DecimalField('Full-Day Rate (USD)', places=2)
    amenities = TextAreaField('Amenities (Comma separated)')
    status = SelectField('Status', choices=[
        ('available', 'Available'),
        ('maintenance', 'Under Maintenance'),
        ('reserved', 'Permanently Reserved')
    ])
    image_url = StringField('Image URL')

class BookingForm(FlaskForm):
    room_id = SelectField('Conference Room', coerce=int, validators=[DataRequired()])
    attendees = IntegerField('Number of Attendees (PAX)', validators=[DataRequired()])
    client_name = StringField('Client Name', validators=[DataRequired()])
    company_name = StringField('Company Name')
    client_id = HiddenField()
    event_type = SelectField('Event Type', choices=[
        ('', 'Select event type...'),
        ('conference', 'Conference'),
        ('meeting', 'Business Meeting'),
        ('workshop', 'Workshop'),
        ('seminar', 'Seminar'),
        ('training', 'Training Session'),
        ('presentation', 'Presentation'),
        ('board_meeting', 'Board Meeting'),
        ('team_building', 'Team Building'),
        ('product_launch', 'Product Launch'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    custom_event_type = StringField('Custom Event Type')
    start_time = DateTimeField('Start Time', format='%Y-%m-%d %H:%M', validators=[DataRequired()])
    end_time = DateTimeField('End Time', format='%Y-%m-%d %H:%M', validators=[DataRequired()])
    notes = TextAreaField('Event Requirements / Special Notes')
    status = SelectField('Status', choices=[
        ('tentative', 'Tentative'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled')
    ], default='tentative')
    
    def validate_end_time(self, field):
        if field.data <= self.start_time.data:
            raise ValidationError('End time must be after start time')
    
    def validate_attendees(self, field):
        if not field.data or not self.room_id.data:
            return
        
        room_data = supabase_select('rooms', filters=[('id', 'eq', self.room_id.data)])
        if not room_data:
            return
        
        room = room_data[0]
        if field.data > room['capacity']:
            flash(f'Warning: Room capacity ({room["capacity"]}) exceeded', 'warning')

class AddonCategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(min=1, max=100)])
    description = TextAreaField('Description')

class AddonForm(FlaskForm):
    name = StringField('Add-on Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    price = DecimalField('Price (USD)', places=2, validators=[DataRequired()])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Active')

class AccommodationForm(FlaskForm):
    room_type = SelectField('Room Type', choices=[
        ('standard', 'Standard Room'),
        ('deluxe', 'Deluxe Room'),
        ('executive', 'Executive Room'),
        ('suite', 'Suite')
    ])
    check_in = DateTimeField('Check-in Date', format='%Y-%m-%d', validators=[DataRequired()])
    check_out = DateTimeField('Check-out Date', format='%Y-%m-%d', validators=[DataRequired()])
    number_of_rooms = IntegerField('Number of Rooms', default=1)
    special_requests = TextAreaField('Special Requests')

class LoginForm(FlaskForm):
    username = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')

class RegistrationForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=2, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[
        ('staff', 'Staff Member'),
        ('manager', 'Manager'),
        ('admin', 'Administrator')
    ], default='staff')

    def validate_email(self, field):
        try:
            existing_users = supabase_admin.table('users').select('email').eq('email', field.data.lower()).execute()
            if existing_users.data:
                raise ValidationError('Email address already registered')
        except Exception as e:
            print(f"Warning: Could not check email uniqueness: {e}")

def get_booking_with_details(booking_id):
    """Get booking with all related details"""
    try:
        # Get booking with relations
        booking_response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(*),
            client:clients(*),
            event_type:event_types(*)
        """).eq('id', booking_id).execute()

        if not booking_response.data:
            return None

        booking = booking_response.data[0]

        # Get user details if created_by is available
        if booking.get('created_by'):
            try:
                user_response = supabase_admin.table('users').select('id, first_name, last_name, username, email').eq('id', booking['created_by']).execute()
                if user_response.data:
                    user = user_response.data[0]
                    # Build full name from first_name and last_name
                    first_name = user.get('first_name', '').strip()
                    last_name = user.get('last_name', '').strip()
                    username = user.get('username', '').strip()
                    email = user.get('email', '').strip()
                    
                    # Prefer full name, then username, then email
                    if first_name and last_name:
                        booking['created_by_name'] = f"{first_name} {last_name}"
                    elif first_name:
                        booking['created_by_name'] = first_name
                    elif username:
                        booking['created_by_name'] = username
                    elif email:
                        booking['created_by_name'] = email
                    else:
                        booking['created_by_name'] = f"User {booking['created_by']}"
                else:
                    booking['created_by_name'] = f"User {booking['created_by']}"
            except Exception as e:
                print(f"⚠️ WARNING: Could not fetch user details: {e}")
                booking['created_by_name'] = f"User {booking['created_by']}"
        else:
            booking['created_by_name'] = 'Unknown User'

        # Get custom addons
        addons_response = supabase_admin.table('booking_custom_addons').select('*').eq('booking_id', booking_id).execute()
        booking['custom_addons'] = addons_response.data if addons_response.data else []

        # Convert datetime strings
        booking = convert_datetime_strings(booking)

        # Calculate totals
        totals = calculate_booking_totals(booking)
        booking.update(totals)

        return booking

    except Exception as e:
        print(f"❌ ERROR: Failed to fetch booking details: {e}")
        return None

# ===============================
# DASHBOARD FUNCTIONS
# ===============================

def get_dashboard_stats():
    """Get comprehensive dashboard statistics"""
    try:
        from datetime import datetime, UTC, timedelta
        
        stats = {
            'total_bookings': 0,
            'total_clients': 0,
            'total_rooms': 0,
            'available_rooms': 0,
            'confirmed_bookings': 0,
            'tentative_bookings': 0,
            'cancelled_bookings': 0,
            'total_revenue': 0,
            'confirmed_revenue': 0,
            'tentative_revenue': 0,
            'revenue_this_month': 0,
            'confirmed_revenue_this_month': 0,
            'tentative_revenue_this_month': 0,
            'average_booking_value': 0,
            'upcoming_bookings': 0,
            'todays_bookings': 0,
            'occupancy_rate': 0,
            'revenue_growth': 0
        }
        
        # Get all bookings
        bookings_response = supabase_admin.table('bookings').select('*').execute()
        all_bookings = bookings_response.data if bookings_response.data else []
        
        # Get total rooms
        rooms_response = supabase_admin.table('rooms').select('*').execute()
        all_rooms = rooms_response.data if rooms_response.data else []
        stats['total_rooms'] = len(all_rooms)
        stats['available_rooms'] = len([r for r in all_rooms if r.get('is_available', True)])
        
        # Get total clients
        clients_response = supabase_admin.table('clients').select('id').execute()
        stats['total_clients'] = len(clients_response.data) if clients_response.data else 0
        
        # Process bookings by status
        non_cancelled_bookings = [b for b in all_bookings if b.get('status') != 'cancelled']
        stats['total_bookings'] = len(non_cancelled_bookings)
        stats['confirmed_bookings'] = len([b for b in all_bookings if b.get('status') == 'confirmed'])
        stats['tentative_bookings'] = len([b for b in all_bookings if b.get('status') == 'tentative'])
        stats['cancelled_bookings'] = len([b for b in all_bookings if b.get('status') == 'cancelled'])
        
        # Calculate revenue metrics
        total_revenue = 0
        confirmed_revenue = 0
        tentative_revenue = 0
        revenue_this_month = 0
        confirmed_revenue_this_month = 0
        tentative_revenue_this_month = 0
        now = datetime.now(UTC)
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        for booking in non_cancelled_bookings:
            booking_revenue = safe_float_conversion(booking.get('total_price', 0))
            booking_status = booking.get('status', 'tentative')
            
            # Add to total revenue
            total_revenue += booking_revenue
            
            # Separate by status
            if booking_status == 'confirmed':
                confirmed_revenue += booking_revenue
            else:  # tentative or any other status
                tentative_revenue += booking_revenue
            
            # Check if booking is this month
            if booking.get('start_time'):
                try:
                    booking_date = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
                    # Ensure both dates are timezone-aware for comparison
                    if booking_date >= current_month_start:
                        revenue_this_month += booking_revenue
                        if booking_status == 'confirmed':
                            confirmed_revenue_this_month += booking_revenue
                        else:
                            tentative_revenue_this_month += booking_revenue
                except Exception:
                    pass
        
        stats['total_revenue'] = total_revenue
        stats['confirmed_revenue'] = confirmed_revenue
        stats['tentative_revenue'] = tentative_revenue
        stats['revenue_this_month'] = revenue_this_month
        stats['confirmed_revenue_this_month'] = confirmed_revenue_this_month
        stats['tentative_revenue_this_month'] = tentative_revenue_this_month
        stats['average_booking_value'] = total_revenue / len(non_cancelled_bookings) if non_cancelled_bookings else 0
        
        # Calculate upcoming bookings (next 30 days)
        next_month = now + timedelta(days=30)
        upcoming_count = 0
        todays_count = 0
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        for booking in non_cancelled_bookings:
            if booking.get('start_time'):
                try:
                    booking_date = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
                    
                    # Count upcoming bookings
                    if now <= booking_date <= next_month:
                        upcoming_count += 1
                    
                    # Count today's bookings
                    if today_start <= booking_date < today_end:
                        todays_count += 1
                        
                except Exception:
                    pass
        
        stats['upcoming_bookings'] = upcoming_count
        stats['todays_bookings'] = todays_count
        
        # Calculate occupancy rate (percentage of rooms with bookings in the last 30 days)
        if stats['total_rooms'] > 0:
            # Look at the last 30 days for a more meaningful occupancy rate
            period_start = now - timedelta(days=30)
            period_end = now
            
            occupied_rooms = set()
            total_bookings_in_period = 0
            
            for booking in non_cancelled_bookings:
                if booking.get('start_time') and booking.get('room_id'):
                    try:
                        booking_date = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
                        # Include bookings from the last 30 days
                        if period_start <= booking_date <= period_end:
                            occupied_rooms.add(booking['room_id'])
                            total_bookings_in_period += 1
                    except Exception as e:
                        print(f"⚠️ Error parsing booking date: {e}")
                        pass
            
            # Calculate as percentage of rooms that had at least one booking in the period
            stats['occupancy_rate'] = (len(occupied_rooms) / stats['total_rooms']) * 100
            print(f"🏨 Occupancy calculation: {len(occupied_rooms)} rooms used out of {stats['total_rooms']} total rooms in last 30 days ({total_bookings_in_period} bookings) = {stats['occupancy_rate']:.1f}%")
        else:
            print("⚠️ No rooms found for occupancy calculation")
            stats['occupancy_rate'] = 0
        
        # Calculate revenue growth (this month vs last month) - using confirmed revenue for accuracy
        last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        last_month_confirmed_revenue = 0
        
        for booking in non_cancelled_bookings:
            if booking.get('start_time') and booking.get('status') == 'confirmed':
                try:
                    booking_date = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
                    if last_month_start <= booking_date < current_month_start:
                        last_month_confirmed_revenue += safe_float_conversion(booking.get('total_price', 0))
                except Exception:
                    pass
        
        if last_month_confirmed_revenue > 0:
            stats['revenue_growth'] = ((confirmed_revenue_this_month - last_month_confirmed_revenue) / last_month_confirmed_revenue) * 100
        else:
            stats['revenue_growth'] = 100 if confirmed_revenue_this_month > 0 else 0
        
        print(f"✅ Dashboard stats calculated: {stats['total_bookings']} bookings, ${stats['total_revenue']:.2f} total revenue (${stats['confirmed_revenue']:.2f} confirmed, ${stats['tentative_revenue']:.2f} tentative), {stats['occupancy_rate']:.1f}% occupancy")
        return stats
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get dashboard stats: {e}")
        error_stats = {
            'total_bookings': 0,
            'total_clients': 0,
            'total_rooms': 0,
            'available_rooms': 0,
            'confirmed_bookings': 0,
            'tentative_bookings': 0,
            'cancelled_bookings': 0,
            'total_revenue': 0,
            'confirmed_revenue': 0,
            'tentative_revenue': 0,
            'revenue_this_month': 0,
            'confirmed_revenue_this_month': 0,
            'tentative_revenue_this_month': 0,
            'average_booking_value': 0,
            'upcoming_bookings': 0,
            'todays_bookings': 0,
            'occupancy_rate': 0,
            'revenue_growth': 0
        }
        return error_stats

def get_recent_bookings(limit=10):
    """Get recent bookings for dashboard with enhanced formatting and error handling"""
    try:
        response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity),
            client:clients(id, contact_person, company_name, email, phone)
        """).order('created_at', desc=True).limit(limit).execute()
        
        if response.data:
            # Convert datetime strings for template compatibility
            bookings = convert_datetime_strings(response.data)
            
            # Enhance booking data for display with better error handling
            for booking in bookings:
                # Ensure client name is available with multiple fallbacks
                if booking.get('client') and isinstance(booking['client'], dict):
                    client = booking['client']
                    company_name = (client.get('company_name') or '').strip()
                    contact_person = (client.get('contact_person') or '').strip()
                    
                    # Priority: company_name > contact_person > fallback
                    if company_name:
                        booking['client_name'] = company_name
                    elif contact_person:
                        booking['client_name'] = contact_person
                    else:
                        booking['client_name'] = 'Client Details Loading...'
                    
                    booking['client_display_name'] = booking['client_name']
                    booking['client_email'] = client.get('email', '')
                else:
                    # Fallback to booking-level client data
                    booking['client_name'] = booking.get('client_name', 'Client Details Loading...')
                    booking['client_display_name'] = booking['client_name']
                    booking['client_email'] = booking.get('client_email', '')
                
                # Ensure room name is available with better error handling
                if booking.get('room') and isinstance(booking['room'], dict):
                    room = booking['room']
                    room_name = (room.get('name') or '').strip()
                    booking['room_name'] = room_name if room_name else 'Room Details Loading...'
                    booking['room_capacity'] = room.get('capacity')
                else:
                    # Fallback to booking-level room data
                    booking['room_name'] = booking.get('room_name', 'Room Details Loading...')
                    booking['room_capacity'] = booking.get('room_capacity')
                
                # Format status for display
                status = booking.get('status', 'tentative')
                booking['status_display'] = status.replace('_', ' ').title()
                
                # Calculate duration for display
                try:
                    from datetime import datetime, UTC
                    if booking.get('start_time') and booking.get('end_time'):
                        if isinstance(booking['start_time'], str):
                            start_time = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
                        else:
                            start_time = booking['start_time']
                        
                        if isinstance(booking['end_time'], str):
                            end_time = datetime.fromisoformat(booking['end_time'].replace('Z', '+00:00'))
                        else:
                            end_time = booking['end_time']
                        
                        duration = end_time - start_time
                        duration_hours = duration.total_seconds() / 3600
                        duration_days = duration.days
                        
                        if duration_days > 0:
                            booking['duration_display'] = f"{duration_days} day{'s' if duration_days != 1 else ''}, {duration_hours % 24:.1f} hours"
                        else:
                            booking['duration_display'] = f"{duration_hours:.1f} hours"
                            
                        booking['duration_hours'] = duration_hours
                    else:
                        booking['duration_display'] = 'Duration TBD'
                        booking['duration_hours'] = 0
                except Exception as e:
                    print(f"⚠️ Error calculating duration for booking {booking.get('id')}: {e}")
                    booking['duration_display'] = 'Duration TBD'
                    booking['duration_hours'] = 0
                
                # Safe total price
                booking['total_price'] = safe_float_conversion(booking.get('total_price', 0))
                
                # Add time ago calculation
                if booking.get('created_at'):
                    from datetime import datetime, UTC
                    created_at = booking['created_at']
                    if isinstance(created_at, str):
                        try:
                            created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00')).replace(tzinfo=None)
                            now = datetime.now(UTC).replace(tzinfo=None)
                            diff = now - created_dt
                            
                            if diff.days > 0:
                                if diff.days == 1:
                                    booking['time_ago'] = "1 day ago"
                                elif diff.days < 7:
                                    booking['time_ago'] = f"{diff.days} days ago"
                                elif diff.days < 30:
                                    weeks = diff.days // 7
                                    booking['time_ago'] = f"{weeks} week{'s' if weeks > 1 else ''} ago"
                                else:
                                    months = diff.days // 30
                                    booking['time_ago'] = f"{months} month{'s' if months > 1 else ''} ago"
                            else:
                                hours = diff.seconds // 3600
                                if hours > 0:
                                    booking['time_ago'] = f"{hours} hour{'s' if hours > 1 else ''} ago"
                                else:
                                    minutes = diff.seconds // 60
                                    if minutes > 0:
                                        booking['time_ago'] = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
                                    else:
                                        booking['time_ago'] = "Just now"
                        except Exception:
                            booking['time_ago'] = "Recently"
                else:
                    booking['time_ago'] = "Recently"
                
                # Add booking title if missing
                if not booking.get('title'):
                    booking['title'] = f"Meeting - {booking['client_name']}"
            
            return bookings
        
        return []
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get recent bookings: {e}")
        return []

def get_upcoming_bookings(limit=10):
    """Get upcoming bookings for dashboard with enhanced formatting and error handling"""
    try:
        from datetime import datetime, UTC, timedelta
        from utils.timezone_utils import get_cat_now, convert_utc_to_cat
        
        # Get bookings starting from now (in CAT)
        now = get_cat_now()
        now_utc = now.astimezone(UTC)
        
        response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity),
            client:clients(id, contact_person, company_name, email, phone)
        """).gte('start_time', now_utc.isoformat()).neq('status', 'cancelled').order('start_time', desc=False).limit(limit).execute()
        
        if response.data:
            # Convert datetime strings for template compatibility
            bookings = convert_datetime_strings(response.data)
            
            # Enhance booking data for display with better error handling
            for booking in bookings:
                # Ensure client name is available with multiple fallbacks
                if booking.get('client') and isinstance(booking['client'], dict):
                    client = booking['client']
                    company_name = (client.get('company_name') or '').strip()
                    contact_person = (client.get('contact_person') or '').strip()
                    
                    # Priority: company_name > contact_person > fallback
                    if company_name:
                        booking['client_name'] = company_name
                    elif contact_person:
                        booking['client_name'] = contact_person
                    else:
                        booking['client_name'] = 'Client Details Loading...'
                    
                    booking['client_display_name'] = booking['client_name']
                    booking['client_email'] = client.get('email', '')
                else:
                    # Fallback to booking-level client data
                    booking['client_name'] = booking.get('client_name', 'Client Details Loading...')
                    booking['client_display_name'] = booking['client_name']
                    booking['client_email'] = booking.get('client_email', '')
                
                # Ensure room name and details are available with better error handling
                if booking.get('room') and isinstance(booking['room'], dict):
                    room = booking['room']
                    room_name = (room.get('name') or '').strip()
                    booking['room_name'] = room_name if room_name else 'Room Details Loading...'
                    booking['room_capacity'] = room.get('capacity')
                else:
                    # Fallback to booking-level room data
                    booking['room_name'] = booking.get('room_name', 'Room Details Loading...')
                    booking['room_capacity'] = booking.get('room_capacity')
                
                # Format status for display
                status = booking.get('status', 'tentative')
                booking['status_display'] = status.replace('_', ' ').title()
                
                # Calculate time until booking (in CAT timezone)
                try:
                    if booking.get('start_time'):
                        if isinstance(booking['start_time'], str):
                            start_time_utc = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
                        else:
                            start_time_utc = booking['start_time']
                        
                        # Convert to CAT for time calculation
                        start_time_cat = convert_utc_to_cat(start_time_utc)
                        time_until = start_time_cat - now
                        
                        if time_until.days > 0:
                            booking['time_until'] = f"in {time_until.days} day{'s' if time_until.days != 1 else ''}"
                        elif time_until.seconds > 3600:
                            hours = time_until.seconds // 3600
                            booking['time_until'] = f"in {hours} hour{'s' if hours != 1 else ''}"
                        else:
                            minutes = time_until.seconds // 60
                            booking['time_until'] = f"in {minutes} minute{'s' if minutes != 1 else ''}"
                    else:
                        booking['time_until'] = 'Time TBD'
                except Exception as e:
                    print(f"⚠️ Error calculating time until booking {booking.get('id')}: {e}")
                    booking['time_until'] = 'Time TBD'
                    booking['time_until'] = 'Time TBD'
                
                # Format status for display
                status = booking.get('status', 'tentative')
                booking['status_display'] = status.replace('_', ' ').title()
                
                # Safe total price
                booking['total_price'] = safe_float_conversion(booking.get('total_price', 0))
                
                # Calculate time until booking and format display
                if booking.get('start_time'):
                    start_time = booking['start_time']
                    if isinstance(start_time, str):
                        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00')).replace(tzinfo=None)
                    
                    time_diff = start_time - now.replace(tzinfo=None)
                    if time_diff.days > 0:
                        if time_diff.days == 1:
                            booking['days_until'] = "Tomorrow"
                        else:
                            booking['days_until'] = f"In {time_diff.days} days"
                    elif time_diff.seconds > 3600:
                        hours = time_diff.seconds // 3600
                        booking['days_until'] = f"In {hours} hour{'s' if hours > 1 else ''}"
                    else:
                        minutes = time_diff.seconds // 60
                        booking['days_until'] = f"In {minutes} minute{'s' if minutes > 1 else ''}"
                    
                    # Format start time for display
                    booking['start_time'] = start_time.strftime('%H:%M')
                    booking['start_date'] = start_time.strftime('%d %b')
                
                # Format end time if available
                if booking.get('end_time'):
                    end_time = booking['end_time']
                    if isinstance(end_time, str):
                        end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00')).replace(tzinfo=None)
                    booking['end_time'] = end_time.strftime('%H:%M')
                
                # Add booking title if missing
                if not booking.get('title'):
                    booking['title'] = f"Meeting - {booking['client_name']}"
            
            return bookings
        
        return []
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get upcoming bookings: {e}")
        return []

def get_todays_bookings():
    """Get today's bookings for dashboard with enhanced formatting"""
    try:
        from datetime import datetime, UTC, timedelta
        
        # Get start and end of today
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity),
            client:clients(id, contact_person, company_name)
        """).gte('start_time', today_start.isoformat()).lt('start_time', today_end.isoformat()).neq('status', 'cancelled').order('start_time').execute()
        
        if response.data:
            # Convert datetime strings for template compatibility
            bookings = convert_datetime_strings(response.data)
            
            # Enhance booking data for display
            for booking in bookings:
                # Ensure client name is available
                if booking.get('client'):
                    client = booking['client']
                    booking['client_name'] = client.get('company_name') or client.get('contact_person', 'Unknown Client')
                    booking['client_display_name'] = booking['client_name']
                else:
                    booking['client_name'] = booking.get('client_name', 'Unknown Client')
                    booking['client_display_name'] = booking['client_name']
                
                # Ensure room name is available
                if booking.get('room'):
                    room = booking['room']
                    booking['room_name'] = room.get('name', 'Unknown Room')
                    booking['room_capacity'] = room.get('capacity')
                else:
                    booking['room_name'] = 'Unknown Room'
                    booking['room_capacity'] = None
                
                # Format status for display
                status = booking.get('status', 'tentative')
                booking['status_display'] = status.replace('_', ' ').title()
                
                # Safe total price
                booking['total_price'] = safe_float_conversion(booking.get('total_price', 0))
                
                # Format time for display
                start_time_formatted = 'TBD'
                end_time_formatted = 'TBD'
                time_range = 'Time TBD'
                
                if booking.get('start_time'):
                    start_time = booking['start_time']
                    if isinstance(start_time, str):
                        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00')).replace(tzinfo=None)
                    start_time_formatted = start_time.strftime('%H:%M')
                
                if booking.get('end_time'):
                    end_time = booking['end_time']
                    if isinstance(end_time, str):
                        end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00')).replace(tzinfo=None)
                    end_time_formatted = end_time.strftime('%H:%M')
                
                # Create time range display
                if start_time_formatted != 'TBD' and end_time_formatted != 'TBD':
                    time_range = f"{start_time_formatted} - {end_time_formatted}"
                elif start_time_formatted != 'TBD':
                    time_range = f"From {start_time_formatted}"
                
                booking['start_time_formatted'] = start_time_formatted
                booking['end_time_formatted'] = end_time_formatted
                booking['time_range'] = time_range
                
                # Add booking title if missing
                if not booking.get('title'):
                    booking['title'] = f"Meeting - {booking['client_name']}"
                
                # Add status indicator for current time
                if start_time_formatted != 'TBD':
                    current_time = now.time()
                    start_time_obj = datetime.strptime(start_time_formatted, '%H:%M').time()
                    
                    if current_time < start_time_obj:
                        booking['status_indicator'] = 'upcoming'
                    elif end_time_formatted != 'TBD':
                        end_time_obj = datetime.strptime(end_time_formatted, '%H:%M').time()
                        if current_time <= end_time_obj:
                            booking['status_indicator'] = 'ongoing'
                        else:
                            booking['status_indicator'] = 'completed'
                    else:
                        booking['status_indicator'] = 'ongoing'
                else:
                    booking['status_indicator'] = 'scheduled'
            
            return bookings
        
        return []
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get today's bookings: {e}")
        return []

def get_revenue_trends():
    """Get revenue trends for dashboard charts"""
    try:
        from datetime import datetime, UTC, timedelta
        import calendar
        
        # Get last 6 months of data
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=180)  # Approximately 6 months
        
        response = supabase_admin.table('bookings').select('*').gte('start_time', start_date.isoformat()).neq('status', 'cancelled').execute()
        
        if not response.data:
            return {
                'monthly_revenue': [],
                'monthly_labels': [],
                'total_revenue': 0,
                'revenue_growth': 0
            }
        
        # Group bookings by month
        monthly_data = {}
        total_revenue = 0
        
        for booking in response.data:
            try:
                start_time = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00')).replace(tzinfo=None)
                month_key = start_time.strftime('%Y-%m')
                month_name = start_time.strftime('%b %Y')
                
                revenue = safe_float_conversion(booking.get('total_price', 0))
                total_revenue += revenue
                
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        'revenue': 0,
                        'label': month_name,
                        'date': start_time
                    }
                
                monthly_data[month_key]['revenue'] += revenue
                
            except Exception as e:
                print(f"⚠️ WARNING: Error processing booking for revenue trends: {e}")
                continue
        
        # Sort by date and prepare chart data
        sorted_months = sorted(monthly_data.items(), key=lambda x: x[1]['date'])
        
        monthly_revenue = [month[1]['revenue'] for month in sorted_months]
        monthly_labels = [month[1]['label'] for month in sorted_months]
        
        # Calculate growth rate (last month vs previous month)
        revenue_growth = 0
        if len(monthly_revenue) >= 2:
            current_month = monthly_revenue[-1]
            previous_month = monthly_revenue[-2]
            if previous_month > 0:
                revenue_growth = ((current_month - previous_month) / previous_month) * 100
        
        return {
            'monthly_revenue': monthly_revenue,
            'monthly_labels': monthly_labels,
            'total_revenue': round(total_revenue, 2),
            'revenue_growth': round(revenue_growth, 1)
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get revenue trends: {e}")
        return {
            'monthly_revenue': [],
            'monthly_labels': [],
            'total_revenue': 0,
            'revenue_growth': 0
        }

# ===============================
# SCHEDULING FUNCTIONS
# ===============================

def should_send_daily_report():
    """
    Check if it's time to send the daily report (5 PM CAT).
    
    Returns:
        bool: True if it's time to send the report
    """
    now = datetime.now(CAT)
    return now.hour == 17 and now.minute == 0  # 5 PM exactly

def run_daily_report_scheduler():
    """
    Simple scheduler function to check if daily report should be sent.
    This can be called from a cron job or scheduled task.
    
    You can set up a cron job to run this every minute:
    * * * * * cd /path/to/your/app && python -c "from core import run_daily_report_scheduler; run_daily_report_scheduler()"
    
    Or on Windows Task Scheduler:
    python -c "from core import run_daily_report_scheduler; run_daily_report_scheduler()"
    """
    try:
        if should_send_daily_report():
            print("📧 Time to send daily report!")
            success = send_daily_report()
            if success:
                print("✅ Daily report sent successfully")
            else:
                print("❌ Failed to send daily report")
        else:
            # Uncomment for debugging
            # print(f"Not time for daily report. Current time: {datetime.now(CAT).strftime('%H:%M')}")
            pass
    except Exception as e:
        print(f"❌ Error in daily report scheduler: {str(e)}")

def test_email_system():
    """
    Test function to verify email system is working.
    Call this function to send a test email.
    """
    try:
        print("🧪 Testing email system...")
        
        # Test basic email
        test_html = """
        <html>
        <body>
            <h2>🧪 Email System Test</h2>
            <p>This is a test email to verify the email system is working correctly.</p>
            <p>Time: {}</p>
            <p>If you receive this, the email system is configured properly!</p>
        </body>
        </html>
        """.format(datetime.now(CAT).strftime('%Y-%m-%d %H:%M %Z'))
        
        success = send_email(
            TEST_EMAIL,
            "🧪 Email System Test",
            test_html,
            "Email System Test - If you receive this, the email system is working!"
        )
        
        if success:
            print("✅ Test email sent successfully!")
            return True
        else:
            print("❌ Failed to send test email")
            return False
            
    except Exception as e:
        print(f"❌ Error testing email system: {str(e)}")
        return False

def test_daily_report():
    """
    Test function to send a daily report immediately (for testing).
    """
    try:
        print("🧪 Testing daily report generation...")
        success = send_daily_report()
        if success:
            print("✅ Test daily report sent successfully!")
            return True
        else:
            print("❌ Failed to send test daily report")
            return False
    except Exception as e:
        print(f"❌ Error testing daily report: {str(e)}")
        return False

# ===============================
# EMAIL CONFIGURATION HELPERS
# ===============================

def print_email_configuration_help():
    """
    Print instructions for configuring email settings.
    """
    print("""
📧 EMAIL CONFIGURATION SETUP

To enable email notifications, you need to configure the following environment variables:

1. EMAIL_HOST=smtp.gmail.com (or your email provider's SMTP server)
2. EMAIL_PORT=587 (usually 587 for TLS)
3. EMAIL_USER=your-email@gmail.com (your email address)
4. EMAIL_PASSWORD=your-app-password (your email app password - NOT your regular password)
5. TEST_EMAIL=your-test-email@gmail.com (where test emails will be sent)

FOR GMAIL:
1. Enable 2-factor authentication on your Google account
2. Go to Google Account settings > Security > App passwords
3. Generate an app password for "Mail"
4. Use this app password in EMAIL_PASSWORD (not your regular password)

ENVIRONMENT VARIABLES SETUP:
- On Windows: Set environment variables in System Properties or use .env file
- On Linux/Mac: Add to ~/.bashrc or use .env file

EXAMPLE .env file:
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=mybusiness@gmail.com
EMAIL_PASSWORD=abcd efgh ijkl mnop
TEST_EMAIL=mytest@gmail.com

TESTING:
Run this in Python console to test:
>>> from core import test_email_system
>>> test_email_system()
    """)

if __name__ == "__main__":
    # This allows you to run email tests directly
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "test-email":
            test_email_system()
        elif sys.argv[1] == "test-report":
            test_daily_report()
        elif sys.argv[1] == "scheduler":
            run_daily_report_scheduler()
        elif sys.argv[1] == "help":
            print_email_configuration_help()
        else:
            print("Available commands: test-email, test-report, scheduler, help")
    else:
        print("Usage: python core.py [test-email|test-report|scheduler|help]")
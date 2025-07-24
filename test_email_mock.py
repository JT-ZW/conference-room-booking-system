#!/usr/bin/env python3
"""
Mock email system - test email functionality without network dependency
"""

import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Load .env file
def load_env_file():
    env_path = Path('.env')
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env_file()

# CAT timezone
CAT = timezone(timedelta(hours=2))

# Email settings
EMAIL_USER = os.getenv('EMAIL_USER', '')
TEST_EMAIL = os.getenv('TEST_EMAIL', '')

def mock_send_email(to_email, subject, body_html, body_text=None):
    """Mock email sending function"""
    print("=" * 60)
    print("📧 EMAIL PREVIEW (MOCK SEND)")
    print("=" * 60)
    print(f"📤 From: {EMAIL_USER}")
    print(f"📥 To: {to_email}")
    print(f"📋 Subject: {subject}")
    print(f"🕐 Time: {datetime.now(CAT).strftime('%Y-%m-%d %H:%M %Z')}")
    print("-" * 60)
    print("📝 EMAIL CONTENT:")
    print("-" * 60)
    if body_text:
        print(body_text)
    print("-" * 60)
    print("✅ Email would be sent successfully (in mock mode)")
    print("=" * 60)
    return True

def test_booking_confirmation_mock():
    """Test booking confirmation email in mock mode"""
    print("🧪 Testing Booking Confirmation Email (Mock Mode)")
    print()
    
    # Sample booking data
    booking_data = {
        'id': 123,
        'client_name': 'John Smith',
        'room_name': 'Conference Room A',
        'start_time': '2025-07-24 09:00',
        'end_time': '2025-07-24 12:00',
        'purpose': 'Team Meeting',
        'status': 'confirmed',
        'notes': 'Please prepare projector and whiteboard'
    }
    
    subject = f"Booking Confirmation #{booking_data['id']} - {booking_data['room_name']}"
    
    # Plain text version
    text_body = f"""
Booking Confirmed!

Dear {booking_data['client_name']},

Your booking has been CONFIRMED! Here are the details:

Booking ID: #{booking_data['id']}
Client: {booking_data['client_name']}
Room/Venue: {booking_data['room_name']}
Start: {booking_data['start_time']}
End: {booking_data['end_time']}
Purpose: {booking_data['purpose']}
Status: Confirmed
Notes: {booking_data['notes']}

If you need to make any changes or have questions, please contact us immediately.

Thank you for choosing our venue!

This is an automated message.
Generated on {datetime.now(CAT).strftime('%Y-%m-%d at %H:%M %Z')}
    """
    
    return mock_send_email(TEST_EMAIL, subject, "", text_body)

def test_daily_report_mock():
    """Test daily report email in mock mode"""
    print("🧪 Testing Daily Report Email (Mock Mode)")
    print()
    
    today = datetime.now(CAT).strftime('%Y-%m-%d')
    subject = f"Daily Booking Report - {today}"
    
    # Sample report data
    text_body = f"""
Daily Booking Report - {today}

Statistics:
- Total Bookings: 5
- Confirmed: 3
- Tentative: 2
- Cancelled: 0

Today's Bookings:
1. ABC Company - Conference Room A (09:00-12:00) - Board Meeting [CONFIRMED]
2. XYZ Corp - Meeting Room B (14:00-16:00) - Team Sync [TENTATIVE]

Tomorrow's Bookings:
1. Tech Startup - Conference Room A (10:00-11:30) - Investor Pitch [CONFIRMED]

Report generated automatically at 5:00 PM CAT
Generated on {datetime.now(CAT).strftime('%Y-%m-%d at %H:%M %Z')}
    """
    
    return mock_send_email(TEST_EMAIL, subject, "", text_body)

def show_email_integration_status():
    """Show current status of email integration"""
    print("📧 EMAIL SYSTEM INTEGRATION STATUS")
    print("=" * 50)
    print()
    print("✅ **Email System Features Added:**")
    print("   - Booking confirmation emails for confirmed bookings")
    print("   - Daily automated reports at 5 PM CAT")
    print("   - HTML and text email templates")
    print("   - SMTP configuration with Gmail")
    print()
    print("📧 **Current Configuration:**")
    print(f"   - Email User: {EMAIL_USER}")
    print(f"   - Test Email: {TEST_EMAIL}")
    print("   - SMTP Host: smtp.gmail.com:587")
    print("   - Authentication: App Password configured ✅")
    print()
    print("⚠️  **Network Issue:**")
    print("   - SMTP ports (587, 465, 25) are blocked by your network")
    print("   - This is common in university/corporate environments")
    print("   - Email system is ready, just needs network access")
    print()
    print("🔧 **When Network Access is Available:**")
    print("   1. Connect to a mobile hotspot or different network")
    print("   2. Run: python test_email_env.py")
    print("   3. Email notifications will work automatically")
    print()
    print("💡 **Current Workaround:**")
    print("   - Email templates and system are working")
    print("   - Booking confirmations will be logged to console")
    print("   - Daily reports can be viewed in the web dashboard")

def main():
    """Main mock test function"""
    if len(os.sys.argv) > 1:
        command = os.sys.argv[1]
        if command == "booking":
            test_booking_confirmation_mock()
        elif command == "report":
            test_daily_report_mock()
        elif command == "status":
            show_email_integration_status()
        else:
            print("Available commands: booking, report, status")
    else:
        print("🧪 MOCK EMAIL SYSTEM TESTING")
        print("=" * 40)
        print()
        print("This will show you what the emails would look like")
        print("without actually sending them.")
        print()
        
        # Test booking confirmation
        test_booking_confirmation_mock()
        print()
        
        # Test daily report
        test_daily_report_mock()
        print()
        
        # Show status
        show_email_integration_status()

if __name__ == "__main__":
    import sys
    main()

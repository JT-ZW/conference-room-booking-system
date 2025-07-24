#!/usr/bin/env python3
"""
Simple test script for email functionality without Flask dependencies
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone

# CAT (Central Africa Time) timezone - UTC+2
CAT = timezone(timedelta(hours=2))

# Email settings - you can add these to your environment variables
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USER = os.getenv('EMAIL_USER', 'your-email@gmail.com')  # Replace with your email
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', 'your-app-password')  # Replace with app password
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'

# Test email address for development
TEST_EMAIL = os.getenv('TEST_EMAIL', 'your-test-email@gmail.com')  # Replace with your test email

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
        
        print(f"✅ Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email to {to_email}: {str(e)}")
        return False

def test_email_system():
    """
    Test function to verify email system is working.
    Call this function to send a test email.
    """
    try:
        print("🧪 Testing email system...")
        print(f"📧 Email Host: {EMAIL_HOST}")
        print(f"📧 Email Port: {EMAIL_PORT}")
        print(f"📧 Email User: {EMAIL_USER}")
        print(f"📧 Test Email: {TEST_EMAIL}")
        
        # Check if email credentials are configured
        if EMAIL_USER == 'your-email@gmail.com' or EMAIL_PASSWORD == 'your-app-password':
            print("⚠️ Email credentials not configured!")
            print("Please set the following environment variables:")
            print("EMAIL_USER=your-email@gmail.com")
            print("EMAIL_PASSWORD=your-app-password")
            print("TEST_EMAIL=your-test-email@gmail.com")
            return False
        
        # Test basic email
        test_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #4CAF50;">🧪 Email System Test</h2>
            <p>This is a test email to verify the email system is working correctly.</p>
            <p><strong>Time:</strong> {datetime.now(CAT).strftime('%Y-%m-%d %H:%M %Z')}</p>
            <p style="color: #2196F3;">If you receive this, the email system is configured properly!</p>
            <hr>
            <p style="font-size: 12px; color: #666;">
                This test was sent from your Conference Room Booking System.
            </p>
        </body>
        </html>
        """
        
        success = send_email(
            TEST_EMAIL,
            "🧪 Email System Test - Conference Room Booking",
            test_html,
            "Email System Test - If you receive this, the email system is working!"
        )
        
        if success:
            print("✅ Test email sent successfully!")
            print(f"📬 Check your inbox at: {TEST_EMAIL}")
            return True
        else:
            print("❌ Failed to send test email")
            return False
            
    except Exception as e:
        print(f"❌ Error testing email system: {str(e)}")
        return False

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
- On PowerShell: 
  $env:EMAIL_USER="mybusiness@gmail.com"
  $env:EMAIL_PASSWORD="abcd efgh ijkl mnop"
  $env:TEST_EMAIL="mytest@gmail.com"

EXAMPLE .env file:
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=mybusiness@gmail.com
EMAIL_PASSWORD=abcd efgh ijkl mnop
TEST_EMAIL=mytest@gmail.com

TESTING:
Run: python test_email.py
    """)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            test_email_system()
        elif sys.argv[1] == "help":
            print_email_configuration_help()
        else:
            print("Available commands: test, help")
    else:
        print("🧪 Email System Test Script")
        print("Usage: python test_email.py [test|help]")
        print("")
        test_email_system()

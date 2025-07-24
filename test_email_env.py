#!/usr/bin/env python3
"""
Test email with .env file support
"""

import os
import sys
from pathlib import Path

# Load .env file if it exists
def load_env_file():
    """Load environment variables from .env file"""
    env_path = Path('.env')
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        print("✅ Loaded environment variables from .env file")
    else:
        print("⚠️ No .env file found")

# Load environment variables
load_env_file()

# Now import our email functions
from test_email import send_email, test_email_system, CAT, TEST_EMAIL, EMAIL_USER, EMAIL_PASSWORD

def test_with_env():
    """Test email system with environment variables"""
    print("🧪 Testing email system with .env configuration...")
    print(f"📧 Email User: {EMAIL_USER}")
    print(f"📧 Test Email: {TEST_EMAIL}")
    print(f"📧 Password configured: {'Yes' if EMAIL_PASSWORD != 'your-app-password' else 'No'}")
    print()
    
    # Check if this looks like a regular password vs app password
    if len(EMAIL_PASSWORD) < 16 and any(c in EMAIL_PASSWORD for c in "!@#$%^&*"):
        print("⚠️  WARNING: You're using what looks like a regular password.")
        print("   For Gmail, you should use an App Password instead.")
        print("   Regular passwords may not work due to security restrictions.")
        print()
        print("📋 To create an App Password for Gmail:")
        print("   1. Go to https://myaccount.google.com/security")
        print("   2. Enable 2-Step Verification if not already enabled")
        print("   3. Click 'App passwords' under '2-Step Verification'")
        print("   4. Generate a password for 'Mail'")
        print("   5. Replace EMAIL_PASSWORD in your .env file with the app password")
        print()
        
        choice = input("Do you want to try with your current password anyway? (y/n): ")
        if choice.lower() != 'y':
            return False
    
    # Try to send test email
    return test_email_system()

if __name__ == "__main__":
    success = test_with_env()
    if success:
        print("\n✅ Email system is working! You can now:")
        print("   - Receive booking confirmation emails")
        print("   - Get automated daily reports at 5 PM")
    else:
        print("\n❌ Email system needs configuration. Please check the instructions above.")

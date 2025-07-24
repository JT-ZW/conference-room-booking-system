#!/usr/bin/env python3
"""
Email connection diagnostic script
"""

import os
import socket
import smtplib
import ssl
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

# Load environment variables
load_env_file()

EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USER = os.getenv('EMAIL_USER', '')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')

def test_network_connectivity():
    """Test basic network connectivity to Gmail SMTP"""
    print("🔍 Testing network connectivity...")
    
    hosts_to_test = [
        ('smtp.gmail.com', 587),
        ('smtp.gmail.com', 465),
        ('google.com', 80),
    ]
    
    for host, port in hosts_to_test:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                print(f"✅ Can connect to {host}:{port}")
            else:
                print(f"❌ Cannot connect to {host}:{port} (error code: {result})")
        except Exception as e:
            print(f"❌ Error connecting to {host}:{port}: {str(e)}")

def test_smtp_connection():
    """Test SMTP connection step by step"""
    print("\n🔍 Testing SMTP connection...")
    
    try:
        print(f"📧 Connecting to {EMAIL_HOST}:{EMAIL_PORT}...")
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=30)
        print("✅ Connected to SMTP server")
        
        print("🔐 Starting TLS...")
        server.starttls()
        print("✅ TLS started successfully")
        
        print("🔑 Attempting login...")
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        print("✅ Login successful!")
        
        server.quit()
        print("✅ SMTP connection test passed!")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication failed: {str(e)}")
        print("💡 Possible solutions:")
        print("   - Check if your App Password is correct")
        print("   - Make sure 2-Factor Authentication is enabled")
        print("   - Try generating a new App Password")
        return False
        
    except smtplib.SMTPConnectError as e:
        print(f"❌ Connection failed: {str(e)}")
        print("💡 Possible solutions:")
        print("   - Check your internet connection")
        print("   - Try a different network (mobile hotspot)")
        print("   - Check firewall settings")
        return False
        
    except smtplib.SMTPServerDisconnected as e:
        print(f"❌ Server disconnected: {str(e)}")
        print("💡 Possible solutions:")
        print("   - Network timeout - try again")
        print("   - Check if antivirus is blocking connection")
        return False
        
    except socket.timeout:
        print("❌ Connection timed out")
        print("💡 Possible solutions:")
        print("   - Network is too slow or unstable")
        print("   - Try a different network")
        print("   - Check if corporate firewall is blocking SMTP")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def test_alternative_smtp_settings():
    """Test alternative SMTP settings"""
    print("\n🔍 Testing alternative SMTP settings...")
    
    alternative_configs = [
        ('smtp.gmail.com', 465, True),  # SSL instead of TLS
        ('smtp.gmail.com', 25, False),  # Alternative port
    ]
    
    for host, port, use_ssl in alternative_configs:
        try:
            print(f"\n📧 Trying {host}:{port} ({'SSL' if use_ssl else 'TLS'})...")
            
            if use_ssl:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(host, port, context=context, timeout=15)
            else:
                server = smtplib.SMTP(host, port, timeout=15)
                server.starttls()
            
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            print(f"✅ Success with {host}:{port}!")
            server.quit()
            
            print(f"\n💡 Working configuration found:")
            print(f"   EMAIL_HOST={host}")
            print(f"   EMAIL_PORT={port}")
            if use_ssl:
                print(f"   Use SMTP_SSL instead of SMTP + starttls")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed with {host}:{port}: {str(e)}")
    
    return False

def show_network_troubleshooting():
    """Show network troubleshooting steps"""
    print("\n🛠️  NETWORK TROUBLESHOOTING STEPS:")
    print("=" * 50)
    print()
    print("1. **Check Internet Connection:**")
    print("   - Try browsing to https://gmail.com")
    print("   - Ping google.com")
    print()
    print("2. **Corporate/University Network Issues:**")
    print("   - Your network may block SMTP ports (25, 587, 465)")
    print("   - Try using a mobile hotspot or different network")
    print("   - Contact IT support about SMTP access")
    print()
    print("3. **Firewall/Antivirus:**")
    print("   - Temporarily disable Windows Firewall")
    print("   - Check antivirus email protection settings")
    print("   - Add Python.exe to firewall exceptions")
    print()
    print("4. **Gmail Account Settings:**")
    print("   - Make sure 2-Factor Authentication is enabled")
    print("   - Generate a new App Password")
    print("   - Try logging into Gmail web interface")
    print()
    print("5. **Alternative Solutions:**")
    print("   - Use a different email provider (Outlook, etc.)")
    print("   - Use email API services (SendGrid, Mailgun)")
    print("   - Set up email forwarding to a working account")

def main():
    """Main diagnostic function"""
    print("📧 EMAIL CONNECTION DIAGNOSTICS")
    print("=" * 40)
    print(f"Email: {EMAIL_USER}")
    print(f"Host: {EMAIL_HOST}:{EMAIL_PORT}")
    print()
    
    # Test 1: Basic network connectivity
    test_network_connectivity()
    
    # Test 2: SMTP connection
    smtp_success = test_smtp_connection()
    
    if not smtp_success:
        # Test 3: Alternative SMTP settings
        alt_success = test_alternative_smtp_settings()
        
        if not alt_success:
            # Show troubleshooting guide
            show_network_troubleshooting()

if __name__ == "__main__":
    main()

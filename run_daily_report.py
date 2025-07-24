#!/usr/bin/env python3
"""
Daily report runner script - can be used with Windows Task Scheduler
"""

import os
import sys
from datetime import datetime

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Change to the script directory
os.chdir(current_dir)

try:
    # Try to import and run daily report from core
    from core import send_daily_report
    
    print(f"🕐 Daily Report Runner - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    success = send_daily_report()
    
    if success:
        print("✅ Daily report sent successfully!")
        sys.exit(0)
    else:
        print("❌ Failed to send daily report")
        sys.exit(1)
        
except ImportError as e:
    # If core import fails, try the test version
    print("⚠️ Core module not available, using test version...")
    from test_scheduler import test_daily_report_email
    
    success = test_daily_report_email()
    
    if success:
        print("✅ Test daily report sent successfully!")
        sys.exit(0)
    else:
        print("❌ Failed to send test daily report")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Error running daily report: {str(e)}")
    sys.exit(1)

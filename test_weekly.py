#!/usr/bin/env python3
"""Test weekly summary functionality"""

import os
import sys
sys.path.append('.')

try:
    from routes.reports import get_weekly_summary_data
    from datetime import datetime, timedelta
    
    print('🔍 Testing weekly summary data function...')
    
    # Test with next week
    current_time = datetime.now()
    tomorrow = current_time + timedelta(days=1)
    
    # Find the start of next week (Monday)
    days_until_monday = (7 - tomorrow.weekday()) % 7
    if days_until_monday == 0:  # If tomorrow is Monday
        start_of_week = tomorrow
    else:
        start_of_week = tomorrow + timedelta(days=days_until_monday)
    
    end_of_week = start_of_week + timedelta(days=6)
    start_date = start_of_week.strftime('%Y-%m-%d')
    end_date = end_of_week.strftime('%Y-%m-%d')
    
    print(f'📅 Testing week: {start_date} to {end_date}')
    
    # Test the function
    weekly_data = get_weekly_summary_data(start_date, end_date)
    print(f'✅ Weekly data generated successfully')
    print(f'📊 Summary: {weekly_data["summary"]}')
    print(f'📅 Week days: {len(weekly_data["week_days"])} days')
    print(f'🏠 Rooms: {len(weekly_data["room_schedule"])} rooms')
    
except Exception as e:
    print(f'❌ Error testing weekly summary: {e}')
    import traceback
    traceback.print_exc()

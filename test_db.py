#!/usr/bin/env python3
"""Test database connection and check schema"""

import os
import sys
sys.path.append('.')

from settings.config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from supabase import create_client

print('🔍 Testing database connection...')
print(f'URL: {SUPABASE_URL}')
print(f'Service Key available: {bool(SUPABASE_SERVICE_KEY)}')

try:
    supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    # Test basic connection with rooms table (which should exist)
    result = supabase_admin.table('rooms').select('*').limit(1).execute()
    print('✅ Database connected successfully')
    print(f'🏠 Rooms table test: {len(result.data)} rows returned')
    
    # Try to query user_activity_log
    try:
        log_result = supabase_admin.table('user_activity_log').select('*').limit(1).execute()
        print(f'📝 user_activity_log table: {len(log_result.data)} rows returned')
        if log_result.data:
            print(f'🔍 Sample log entry columns: {list(log_result.data[0].keys())}')
    except Exception as e:
        print(f'⚠️ user_activity_log table issue: {e}')
        
except Exception as e:
    print(f'❌ Database error: {e}')

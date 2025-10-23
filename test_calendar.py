#!/usr/bin/env python3
"""Test script to check if calendar view works after fixing the database schema issue"""

try:
    from routes.bookings import calendar_view
    print("✅ Calendar view import successful")
    
    # Test the SQL query structure
    from settings.config import get_supabase_admin_client
    supabase_admin = get_supabase_admin_client()
    
    # Test a simple query to clients table to verify schema
    response = supabase_admin.table('clients').select('id, contact_person, company_name').limit(1).execute()
    if response.data:
        print("✅ Clients table query successful")
        print(f"✅ Sample client data: {response.data[0]}")
    else:
        print("⚠️ No clients found in database")
        
except Exception as e:
    print(f"❌ Error: {e}")

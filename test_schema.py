#!/usr/bin/env python3
"""Test script to verify the database schema for bookings table"""

try:
    from settings.config import supabase_admin
    
    # Test a simple query to bookings table to see what columns exist
    response = supabase_admin.table('bookings').select('*').limit(1).execute()
    if response.data:
        print("✅ Bookings table query successful")
        print(f"✅ Available columns in bookings: {list(response.data[0].keys())}")
    else:
        print("⚠️ No bookings found in database")
        
    # Test the calendar query structure
    response = supabase_admin.table('bookings').select('''
        *,
        room:rooms(id, name, capacity),
        client:clients(id, contact_person, company_name)
    ''').limit(1).execute()
    
    if response.data:
        print("✅ Calendar query structure successful")
    else:
        print("⚠️ Calendar query returned no data")
        
except Exception as e:
    print(f"❌ Error: {e}")

#!/usr/bin/env python3
"""
Test script for dashboard API functionality
"""
import sys
import traceback
from datetime import datetime, UTC, timedelta

# Add the current directory to Python path
sys.path.insert(0, '.')

try:
    from core import supabase_admin
    print("✅ Successfully imported supabase_admin")
    
    # Test basic connectivity
    print("\n🔍 Testing Supabase connectivity...")
    
    # Test bookings table
    print("\n📊 Testing bookings table...")
    today = datetime.now(UTC).date()
    start_of_today = datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC)
    end_of_today = datetime.combine(today, datetime.max.time()).replace(tzinfo=UTC)
    
    today_bookings = supabase_admin.table('bookings').select(
        'id, start_time, status'
    ).gte('start_time', start_of_today.isoformat()).lte('start_time', end_of_today.isoformat()).execute()
    
    print(f"Found {len(today_bookings.data)} bookings for today")
    
    # Test rooms table
    print("\n🏨 Testing rooms table...")
    rooms_response = supabase_admin.table('rooms').select(
        'id, name'
    ).execute()
    
    print(f"Found {len(rooms_response.data)} rooms total")
    # For now, assume all rooms are available since we don't know the exact schema
    active_rooms = len(rooms_response.data)
    print(f"Found {active_rooms} available rooms")
    
    # Test weekly revenue calculation
    print("\n💰 Testing weekly revenue calculation...")
    week_start = today - timedelta(days=7)
    week_start_dt = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=UTC)
    
    weekly_bookings = supabase_admin.table('bookings').select(
        'id, total_price, start_time, status'
    ).gte('start_time', week_start_dt.isoformat()).execute()
    
    weekly_revenue = sum(
        float(booking['total_price'] or 0) 
        for booking in weekly_bookings.data 
        if booking['status'] == 'confirmed'
    )
    
    print(f"Found {len(weekly_bookings.data)} bookings in last 7 days")
    print(f"Weekly revenue: ${weekly_revenue:,.2f}")
    
    # Calculate utilization
    total_rooms = len(rooms_response.data)
    utilization = 0
    if total_rooms > 0:
        weekly_booked_days = len(weekly_bookings.data)
        total_capacity = total_rooms * 7  # 7 days
        utilization = min(100, (weekly_booked_days / total_capacity * 100)) if total_capacity > 0 else 0
    
    print(f"Utilization: {utilization:.1f}%")
    
    print("\n✅ All database tests passed!")
    print("\nDashboard stats preview:")
    print(f"  Today's Events: {len([b for b in today_bookings.data if b['status'] in ['confirmed', 'checked_in']])}")
    print(f"  Weekly Revenue: ${int(weekly_revenue):,}")
    print(f"  Active Rooms: {active_rooms}")
    print(f"  Utilization: {utilization:.1f}%")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the correct directory with virtual environment activated")
except Exception as e:
    print(f"❌ Error: {e}")
    print(f"Full traceback:\n{traceback.format_exc()}")

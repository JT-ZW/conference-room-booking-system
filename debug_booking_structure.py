#!/usr/bin/env python3
"""
Debug script to check booking data structure
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client
import json

# Load environment variables
load_dotenv()

# Initialize Supabase
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')

supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def test_booking_structure():
    """Test the booking data structure"""
    try:
        # Get a recent booking with details
        booking_response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(*),
            client:clients(*),
            event_type:event_types(*)
        """).order('created_at', desc=True).limit(1).execute()

        if booking_response.data:
            booking = booking_response.data[0]
            print("🔍 Booking structure:")
            print(json.dumps(booking, indent=2, default=str))
            
            print("\n📊 Key checks:")
            print(f"- Has 'client' key: {'client' in booking}")
            print(f"- Client value: {booking.get('client')}")
            print(f"- Client type: {type(booking.get('client'))}")
            
            print(f"- Has 'room' key: {'room' in booking}")
            print(f"- Room value: {booking.get('room')}")
            print(f"- Room type: {type(booking.get('room'))}")
            
        else:
            print("❌ No bookings found")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    test_booking_structure()

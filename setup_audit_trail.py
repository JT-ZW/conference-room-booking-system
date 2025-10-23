#!/usr/bin/env python3
"""
Script to create the booking audit trail table in Supabase
"""

def create_audit_table():
    """Create the booking audit trail table"""
    try:
        from core import supabase_admin
        
        # SQL to create the audit trail table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS booking_audit_trail (
            id SERIAL PRIMARY KEY,
            booking_id INTEGER NOT NULL,
            user_id TEXT,
            user_name TEXT,
            action_type TEXT NOT NULL,
            field_changed TEXT,
            old_value TEXT,
            new_value TEXT,
            change_summary TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        -- Create indexes for better performance
        CREATE INDEX IF NOT EXISTS idx_booking_audit_booking_id ON booking_audit_trail(booking_id);
        CREATE INDEX IF NOT EXISTS idx_booking_audit_created_at ON booking_audit_trail(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_booking_audit_user_id ON booking_audit_trail(user_id);
        CREATE INDEX IF NOT EXISTS idx_booking_audit_action_type ON booking_audit_trail(action_type);
        """
        
        # Execute the SQL
        result = supabase_admin.rpc('exec_sql', {'sql': create_table_sql}).execute()
        
        if result.data:
            print("✅ Booking audit trail table created successfully!")
            print("📋 Table structure:")
            print("   - id (Primary key)")
            print("   - booking_id (Foreign key to bookings)")
            print("   - user_id (User who made the change)")
            print("   - user_name (Display name of user)")
            print("   - action_type (created, updated, status_changed, etc.)")
            print("   - field_changed (specific field that changed)")
            print("   - old_value (previous value)")
            print("   - new_value (new value)")
            print("   - change_summary (human-readable description)")
            print("   - ip_address (IP address of user)")
            print("   - user_agent (Browser information)")
            print("   - created_at (timestamp)")
            print("\n📊 Indexes created for optimal performance")
            return True
        else:
            print("❌ Failed to create audit trail table")
            return False
            
    except Exception as e:
        print(f"❌ Error creating audit trail table: {e}")
        print("💡 You may need to run the SQL manually in your Supabase dashboard:")
        print("\n" + "="*60)
        with open('sql_booking_audit_trail.sql', 'r') as f:
            print(f.read())
        print("="*60)
        return False

if __name__ == "__main__":
    print("🔍 Creating booking audit trail table...")
    print("📊 Environment: Supabase Database")
    print()
    
    success = create_audit_table()
    
    if success:
        print("\n🎉 Setup complete! The audit trail system is ready to use.")
        print("📝 All booking changes will now be tracked automatically.")
    else:
        print("\n⚠️ Manual setup required. Please check the instructions above.")

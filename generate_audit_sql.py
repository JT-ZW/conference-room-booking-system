#!/usr/bin/env python3
"""
SQL Script Generator for Booking Audit Trail Table
Run this to get the exact SQL commands to paste into your Supabase SQL editor
"""

def generate_sql():
    """Generate SQL commands for audit trail table"""
    
    sql_commands = """
-- =====================================================
-- BOOKING AUDIT TRAIL TABLE SETUP
-- Copy and paste these commands into your Supabase SQL Editor
-- =====================================================

-- 1. Create the booking_audit_trail table
CREATE TABLE IF NOT EXISTS booking_audit_trail (
    id BIGSERIAL PRIMARY KEY,
    booking_id BIGINT NOT NULL,
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

-- 2. Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_booking_audit_booking_id ON booking_audit_trail(booking_id);
CREATE INDEX IF NOT EXISTS idx_booking_audit_created_at ON booking_audit_trail(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_booking_audit_user_id ON booking_audit_trail(user_id);
CREATE INDEX IF NOT EXISTS idx_booking_audit_action_type ON booking_audit_trail(action_type);

-- 3. Add comments for documentation
COMMENT ON TABLE booking_audit_trail IS 'Tracks all changes made to bookings for audit purposes';
COMMENT ON COLUMN booking_audit_trail.action_type IS 'Type of action: created, updated, status_changed, cancelled, etc.';
COMMENT ON COLUMN booking_audit_trail.field_changed IS 'Specific field that was changed';
COMMENT ON COLUMN booking_audit_trail.change_summary IS 'Human-readable description of what changed';

-- 4. Enable Row Level Security (RLS) - Optional but recommended
ALTER TABLE booking_audit_trail ENABLE ROW LEVEL SECURITY;

-- 5. Create a policy to allow authenticated users to read audit trails
CREATE POLICY IF NOT EXISTS "Allow authenticated users to read audit trail" ON booking_audit_trail
FOR SELECT USING (auth.role() = 'authenticated');

-- 6. Create a policy to allow service role to insert audit records
CREATE POLICY IF NOT EXISTS "Allow service role to insert audit records" ON booking_audit_trail
FOR INSERT WITH CHECK (true);

-- 7. Insert a test record to verify the table works
INSERT INTO booking_audit_trail (
    booking_id, 
    user_name, 
    action_type, 
    change_summary
) VALUES (
    1, 
    'System Setup', 
    'table_created', 
    'Audit trail table created and configured'
);

-- =====================================================
-- SETUP COMPLETE!
-- The audit trail system is now ready to use.
-- =====================================================
"""
    
    return sql_commands

if __name__ == "__main__":
    print("🔧 BOOKING AUDIT TRAIL - DATABASE SETUP")
    print("=" * 50)
    print()
    print("📋 INSTRUCTIONS:")
    print("1. Copy the SQL commands below")
    print("2. Go to your Supabase Dashboard")
    print("3. Navigate to SQL Editor")
    print("4. Paste and run the commands")
    print("5. Refresh your booking page to see the audit trail working")
    print()
    print("🔧 SQL COMMANDS TO RUN:")
    print("=" * 50)
    
    sql = generate_sql()
    print(sql)
    
    # Also save to file
    with open('audit_trail_setup.sql', 'w') as f:
        f.write(sql)
    
    print("=" * 50)
    print("💾 SQL commands also saved to: audit_trail_setup.sql")
    print("🎯 After running these commands, the audit trail will work automatically!")

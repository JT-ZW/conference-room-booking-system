-- Booking Audit Trail Table
-- This table tracks all changes made to bookings including who made them, when, and what changed

CREATE TABLE booking_audit_trail (
    id SERIAL PRIMARY KEY,
    booking_id INTEGER NOT NULL,
    user_id TEXT,
    user_name TEXT,
    action_type TEXT NOT NULL, -- 'created', 'updated', 'status_changed', 'cancelled'
    field_changed TEXT, -- specific field that was changed (e.g., 'status', 'room_id', 'start_time')
    old_value TEXT, -- previous value (JSON string for complex fields)
    new_value TEXT, -- new value (JSON string for complex fields)
    change_summary TEXT, -- human-readable description of the change
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Foreign key relationship (assuming bookings table exists)
    CONSTRAINT fk_booking_audit_booking_id 
        FOREIGN KEY (booking_id) 
        REFERENCES bookings(id) 
        ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX idx_booking_audit_booking_id ON booking_audit_trail(booking_id);
CREATE INDEX idx_booking_audit_created_at ON booking_audit_trail(created_at DESC);
CREATE INDEX idx_booking_audit_user_id ON booking_audit_trail(user_id);
CREATE INDEX idx_booking_audit_action_type ON booking_audit_trail(action_type);

-- Optional: Create a view for easy querying with user-friendly formatting
CREATE VIEW booking_audit_trail_view AS
SELECT 
    bat.id,
    bat.booking_id,
    b.title as booking_title,
    bat.user_id,
    bat.user_name,
    bat.action_type,
    bat.field_changed,
    bat.old_value,
    bat.new_value,
    bat.change_summary,
    bat.created_at,
    bat.ip_address
FROM booking_audit_trail bat
LEFT JOIN bookings b ON bat.booking_id = b.id
ORDER BY bat.created_at DESC;

-- Add comments for documentation
COMMENT ON TABLE booking_audit_trail IS 'Tracks all changes made to bookings for audit purposes';
COMMENT ON COLUMN booking_audit_trail.action_type IS 'Type of action: created, updated, status_changed, cancelled, etc.';
COMMENT ON COLUMN booking_audit_trail.field_changed IS 'Specific field that was changed';
COMMENT ON COLUMN booking_audit_trail.change_summary IS 'Human-readable description of what changed';

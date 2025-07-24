-- Create the user_activity_log table in your Supabase database
CREATE TABLE user_activity_log (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    user_name VARCHAR(255) NOT NULL,
    user_email VARCHAR(255),
    activity_type VARCHAR(100) NOT NULL,
    activity_description TEXT NOT NULL,
    resource_type VARCHAR(50), -- e.g., 'booking', 'room', 'client', 'addon'
    resource_id INTEGER, -- ID of the affected resource
    ip_address INET,
    user_agent TEXT,
    session_id VARCHAR(255),
    status VARCHAR(20) DEFAULT 'success', -- 'success', 'failed', 'warning'
    metadata JSONB, -- Additional context data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX idx_user_activity_log_user_id ON user_activity_log(user_id);
CREATE INDEX idx_user_activity_log_created_at ON user_activity_log(created_at);
CREATE INDEX idx_user_activity_log_activity_type ON user_activity_log(activity_type);
CREATE INDEX idx_user_activity_log_resource ON user_activity_log(resource_type, resource_id);

-- Enable RLS (Row Level Security) if you want users to only see their own logs
ALTER TABLE user_activity_log ENABLE ROW LEVEL SECURITY;

-- Optional: Policy to allow users to see only their own activity
CREATE POLICY "Users can view own activity" ON user_activity_log
    FOR SELECT USING (auth.uid() = user_id);

-- Admin policy to view all activities (adjust based on your admin role setup)
CREATE POLICY "Admins can view all activity" ON user_activity_log
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM users 
            WHERE id = auth.uid() 
            AND role IN ('admin', 'manager')
        )
    );
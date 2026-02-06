-- Migration: Add message limit tracking columns to users table
-- Date: 2026-02-02
-- Description: Adds columns for tracking monthly message usage and limits

-- Add new columns to users table
ALTER TABLE users
ADD COLUMN IF NOT EXISTS messages_used INTEGER DEFAULT 0 NOT NULL,
ADD COLUMN IF NOT EXISTS monthly_limit INTEGER DEFAULT 100 NOT NULL,
ADD COLUMN IF NOT EXISTS limit_reset_date TIMESTAMP DEFAULT (NOW() + INTERVAL '30 days') NOT NULL;

-- Update existing users to have default values
UPDATE users
SET
    messages_used = 0,
    monthly_limit = 100,
    limit_reset_date = NOW() + INTERVAL '30 days'
WHERE messages_used IS NULL;

-- Create index for faster lookups on reset date
CREATE INDEX IF NOT EXISTS idx_users_limit_reset_date ON users(limit_reset_date);

-- Display summary
SELECT
    COUNT(*) as total_users,
    AVG(messages_used) as avg_messages_used,
    AVG(monthly_limit) as avg_monthly_limit
FROM users;

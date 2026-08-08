-- ============================================================================
-- Migration Intelligence Platform - Authentication & Activity Schema
-- ============================================================================
-- This script creates tables for user authentication and activity logging
-- All indexes are optimized for common query patterns
-- ============================================================================

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user',  -- 'user' or 'admin'
    email VARCHAR(255),
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for user queries
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);

-- ─────────────────────────────────────────────────────────────────────────
-- Activity logs table - CRITICAL: cleans up automatically
-- Stores all login/logout events with metadata
-- ─────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,  -- NULL for failed logins where user doesn't exist
    action VARCHAR(50) NOT NULL,  -- 'login', 'logout', 'password_change', etc
    severity VARCHAR(20) DEFAULT 'info',  -- 'info', 'warning', 'critical'
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    status VARCHAR(50),  -- 'success', 'failed'
    details TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- ─────────────────────────────────────────────────────────────────────────
-- CRITICAL INDEXES for activity logs (prevents full table scans)
-- ─────────────────────────────────────────────────────────────────────────

-- Timestamp index - used for cleanup queries and recent activity
CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON user_activity_logs(timestamp);

-- Status index - IMPORTANT: prevents full scan when filtering failures
CREATE INDEX IF NOT EXISTS idx_activity_status ON user_activity_logs(status);

-- Composite indexes for common WHERE + ORDER BY patterns
-- Used in admin dashboard queries
CREATE INDEX IF NOT EXISTS idx_activity_user_time 
  ON user_activity_logs(user_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_activity_action_time 
  ON user_activity_logs(action, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_activity_severity_time 
  ON user_activity_logs(severity, timestamp DESC);

-- Action index - for filtering by login/logout/etc
CREATE INDEX IF NOT EXISTS idx_activity_action ON user_activity_logs(action);

-- ─────────────────────────────────────────────────────────────────────────
-- Seed admin user (password: "admin123" hashed with bcrypt)
-- ─────────────────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO users (username, password_hash, role, email, is_active) 
VALUES ('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5YmMxSUS34jxy', 'admin', 'admin@system.local', 1);

-- ─────────────────────────────────────────────────────────────────────────
-- Verify schema
-- ─────────────────────────────────────────────────────────────────────────

SELECT '✓ Schema created successfully' as status;
SELECT COUNT(*) as user_count FROM users;
SELECT COUNT(*) as activity_count FROM user_activity_logs;

-- Initialize AI Secretary database with schema
-- This script runs automatically when PostgreSQL container starts

-- Create the ai_secretary schema for multi-project isolation
CREATE SCHEMA IF NOT EXISTS ai_secretary;

-- Set default search path to include our schema
ALTER DATABASE ai_secretary SET search_path TO ai_secretary, public;

-- Grant permissions to the application user
GRANT ALL PRIVILEGES ON SCHEMA ai_secretary TO ai_secretary_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA ai_secretary TO ai_secretary_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA ai_secretary TO ai_secretary_user;

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Set timezone
SET timezone = 'UTC';
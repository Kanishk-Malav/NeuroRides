-- Initialize NeuroRides database with PostGIS extension
-- This script runs when the database container is first created

-- Create the PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Create additional useful extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Set timezone
SET timezone = 'UTC';

-- Create indexes for better performance
-- These will be created by Django migrations, but we can prepare the database

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE neurorides TO neurorides;

-- Create a read-only user for analytics (optional)
-- CREATE USER neurorides_readonly WITH PASSWORD 'readonly123';
-- GRANT CONNECT ON DATABASE neurorides TO neurorides_readonly;
-- GRANT USAGE ON SCHEMA public TO neurorides_readonly;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO neurorides_readonly;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO neurorides_readonly;
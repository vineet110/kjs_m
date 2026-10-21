-- PostgreSQL initialization script
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS analytics;

-- Read-only role for Superset
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles WHERE rolname = 'kjs_readonly') THEN
      CREATE ROLE kjs_readonly WITH LOGIN PASSWORD 'kjs_readonly_pass';
   END IF;
END
$do$;

GRANT USAGE ON SCHEMA analytics TO kjs_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO kjs_readonly;

-- What the app's own database user (kjs_app) may do. Run after every migration (deploy.sh and
-- restore.sh do it). Safe to run again and again.
--
-- Why a separate user: the owner "kjs" can do anything (drop tables, run server commands).
-- The app only needs to read and write rows, so if the app is ever tricked into running bad SQL,
-- the damage stops there. Migrations still run as "kjs" (MIGRATION_DATABASE_URL).

GRANT CONNECT ON DATABASE kjs TO kjs_app;
GRANT USAGE ON SCHEMA public TO kjs_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO kjs_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO kjs_app;

-- Tables created by future migrations get the same rights automatically
ALTER DEFAULT PRIVILEGES FOR ROLE kjs IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO kjs_app;
ALTER DEFAULT PRIVILEGES FOR ROLE kjs IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO kjs_app;

-- The audit log is append-only: the app may add rows, never change or remove them
-- (a trigger blocks this too; this is the second lock on the same door).
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM kjs_app;

-- Alembic's bookkeeping table is for migrations only
REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM kjs_app;

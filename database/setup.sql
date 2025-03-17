-- run as superuser:
CREATE EXTENSION pg_cron IF NOT EXISTS;

-- optionally, grant usage to regular users:
GRANT USAGE ON SCHEMA cron TO marco;
DROP SCHEMA IF EXISTS contacts CASCADE;

DROP SCHEMA IF EXISTS security CASCADE;

DROP SCHEMA IF EXISTS cron CASCADE;

CREATE SCHEMA security;
CREATE SCHEMA contacts;

CREATE EXTENSION pg_cron;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA PUBLIC;
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA PUBLIC;

CREATE OR REPLACE FUNCTION contacts.uuid_generate_v4()
RETURNS uuid AS
$$
SELECT public.uuid_generate_v4();
$$ LANGUAGE sql;

CREATE OR REPLACE FUNCTION security.uuid_generate_v4()
RETURNS uuid AS
$$
SELECT public.uuid_generate_v4();
$$ LANGUAGE sql;

CREATE OR REPLACE FUNCTION security.gen_random_bytes(length integer)
RETURNS bytea AS
$$
SELECT public.gen_random_bytes(length);
$$ LANGUAGE sql;

GRANT USAGE ON SCHEMA cron TO test; -- need to get in env

-- GRANT USAGE ON SCHEMA cron TO postgres;

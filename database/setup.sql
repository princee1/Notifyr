-- Active: 1740679093248@@localhost@5432@notifyr
-- DROP SCHEMA IF EXISTS contacts CASCADE;

-- DROP SCHEMA IF EXISTS security CASCADE;

-- DROP SCHEMA IF EXISTS links CASCADE;

-- DROP SCHEMA IF EXISTS emails CASCADE;

-- DROP SCHEMA IF EXISTS cron CASCADE;

CREATE SCHEMA security;

CREATE SCHEMA contacts;

CREATE SCHEMA emails;

CREATE SCHEMA links;

-- CREATE SCHEMA mta;

-- CREATE SCHEMA notifications;

CREATE SCHEMA twilio;

-- CREATE SCHEMA campaigns;

CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA PUBLIC;
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA PUBLIC;

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA contacts; 

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

CREATE OR REPLACE FUNCTION security.uuid_generate_v1mc()
RETURNS uuid AS
$$
SELECT public.uuid_generate_v1mc();
$$ LANGUAGE sql;

CREATE OR REPLACE FUNCTION contacts.uuid_generate_v1mc()
RETURNS uuid AS
$$
SELECT public.uuid_generate_v1mc();
$$ LANGUAGE sql;

CREATE OR REPLACE FUNCTION links.uuid_generate_v1mc()
RETURNS uuid AS
$$
SELECT public.uuid_generate_v1mc();
$$ LANGUAGE sql;


CREATE OR REPLACE FUNCTION emails.uuid_generate_v1mc()
RETURNS uuid AS
$$
SELECT public.uuid_generate_v1mc();
$$ LANGUAGE sql;


CREATE OR REPLACE FUNCTION twilio.uuid_generate_v1mc()
RETURNS uuid AS
$$
SELECT public.uuid_generate_v1mc();
$$ LANGUAGE sql;


CREATE OR REPLACE FUNCTION security.gen_random_bytes(length integer)
RETURNS bytea AS
$$
SELECT public.gen_random_bytes(length);
$$ LANGUAGE sql;

GRANT USAGE ON SCHEMA cron TO test; -- need to get in env

-- GRANT USAGE ON SCHEMA cron TO postgres;

CREATE DOMAIN public.DeviceType AS VARCHAR(50) CHECK (
    VALUE IN (
    'desktop',
    'smartphone',
    'tablet',
    'feature phone',
    'console',
    'tv',
    'car browser',
    'smart display',
    'camera',
    'portable media player',
    'phablet',
    'smartwatch',
    'ebook reader',
    'unknown'
        
    )
);

-- APP ROLE

CREATE ROLE vault_ntrfyr_app_role;

GRANT CONNECT ON DATABASE notifyr TO vault_ntrfyr_app_role;

GRANT USAGE ON SCHEMA contacts, security, public, links, twilio, emails TO vault_ntrfyr_app_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA contacts, security, public, links, twilio, emails TO vault_ntrfyr_app_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA contacts, security, public, links, twilio, emails
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO vault_ntrfyr_app_role;

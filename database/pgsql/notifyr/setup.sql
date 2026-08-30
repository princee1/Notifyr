-- Active: 1740679093248@@localhost@5432@notifyr
-- DROP SCHEMA IF EXISTS contacts CASCADE;

-- DROP SCHEMA IF EXISTS security CASCADE;

-- DROP SCHEMA IF EXISTS links CASCADE;

-- DROP SCHEMA IF EXISTS emails CASCADE;

-- DROP SCHEMA IF EXISTS cron CASCADE;

CREATE EXTENSION IF NOT EXISTS pg_cron;

GRANT USAGE ON SCHEMA cron TO test; -- need to get in env

CREATE SCHEMA contacts;

CREATE SCHEMA emails;

CREATE SCHEMA links;

-- CREATE SCHEMA mta;

-- CREATE SCHEMA notifications;

CREATE SCHEMA twilio;

-- CREATE SCHEMA campaigns;

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA contacts; 

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

CREATE ROLE vault_ntfr_app_role NOLOGIN;

CREATE ROLE vault_ntfr_admin_role NOLOGIN;

-- Grants the ability to execute CREATE SCHEMA commands in the database.
GRANT CONNECT ON DATABASE notifyr TO vault_ntfr_app_role;

-- Grants basic connect permission
GRANT CONNECT ON DATABASE notifyr TO vault_ntfr_admin_role;

GRANT CREATE ON DATABASE notifyr TO vault_ntfr_admin_role;

CALL bootstrap_admin.grant_app_role_privileges('vault_ntfr_app_role',ARRAY['public','contacts','emails','links','twilio']);

CALL bootstrap_admin.grant_admin_role_privileges('vault_ntfr_admin_role',ARRAY['public','contacts','emails','links','twilio']);

DROP SCHEMA bootstrap_admin CASCADE;


CREATE EXTENSION IF NOT EXISTS pg_cron;

GRANT USAGE ON SCHEMA cron TO test; -- need to get in env

SET search_path = cron;

CREATE OR REPLACE FUNCTION cron.clear_job_details() RETURNS VOID AS $$
BEGIN
    SET search_path = cron;
    DELETE FROM cron.job_run_details;
END $$ LANGUAGE PLPGSQL;

SELECT cron.schedule (
        'clear job details', '0 0 * * 0', 'SELECT cron.clear_job_details();'
    );


CREATE SCHEMA clients;

CREATE ROLE vault_ntfr_client_role NOLOGIN;

CREATE ROLE vault_ntfr_admin_client_role NOLOGIN;

GRANT CONNECT ON DATABASE security TO vault_ntfr_client_role;

GRANT CREATE ON DATABASE security TO vault_ntfr_admin_client_role;

GRANT CREATE ON DATABASE security TO vault_ntfr_admin_client_role;

CALL bootstrap_admin.grant_app_role_privileges('vault_ntfr_client_role',ARRAY['clients','public']);

CALL bootstrap_admin.grant_admin_role_privileges('vault_ntfr_admin_client_role',ARRAY['clients','public']);

DROP SCHEMA bootstrap_admin CASCADE;

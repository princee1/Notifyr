CREATE SCHEMA clients;

CREATE ROLE vault_ntfr_client_role NOLOGIN;

CREATE ROLE vault_ntfr_admin_client_role NOLOGIN;

GRANT CONNECT ON DATABASE security TO vault_ntfr_client_role;

GRANT CREATE ON DATABASE security TO vault_ntfr_admin_client_role;

GRANT CREATE ON DATABASE security TO vault_ntfr_admin_client_role;

CALL bootstrap_admin.grant_app_role_privileges('vault_ntfr_client_role',ARRAY['clients','public']);

CALL bootstrap_admin.grant_admin_role_privileges('vault_ntfr_admin_client_role',ARRAY['clients','public']);

DROP SCHEMA bootstrap_admin CASCADE;

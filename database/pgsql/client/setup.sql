
CREATE SCHEMA security;

CREATE ROLE vault_ntfr_client_role NOLOGIN;

CREATE ROLE vault_ntfr_admin_client_role NOLOGIN;

GRANT CONNECT ON DATABASE notifyr TO vault_ntfr_client_role;

GRANT CREATE ON DATABASE notifyr TO vault_ntfr_admin_client_role;

GRANT CREATE ON DATABASE notifyr TO vault_ntfr_admin_client_role;

CALL bootstrap_admin.grant_app_role_privileges('vault_ntfr_client_role',ARRAY['security','public'])

CALL bootstrap_admin.grant_admin_role_privileges('vault_ntfr_admin_client_role',ARRAY['security','public'])

DROP SCHEMA bootstrap_admin CASCADE;

-- #######################################################################
-- # PostgreSQL SQL Script: vault_ntrfyr_admin_role setup                #
-- # Purpose: Creates a high-privilege role for temporary Vault users.   #
-- # NOTE: Run this script while connected to the target database as a   #
-- # superuser (e.g., 'postgres').                                      #
-- #######################################################################

\echo '--- Creating Group Role ---'
CREATE ROLE vault_ntrfyr_admin_role NOLOGIN;

\echo '--- Granting Database-Level Privileges ---'
-- Grants the ability to execute CREATE SCHEMA commands in the database.
GRANT CREATE ON DATABASE notifyr TO vault_ntrfyr_admin_role;

-- Grants basic connect permission
GRANT CONNECT ON DATABASE notifyr TO vault_ntrfyr_admin_role;


-- #######################################################################
-- # Section 1: Permissions on CURRENT Schemas and Objects (6 Schemas)   #
-- # These commands must be run for every existing schema.               #
-- #######################################################################

\echo '--- Granting ALL Privileges to existing schema: contacts ---'
GRANT USAGE ON SCHEMA contacts TO vault_ntrfyr_admin_role;
GRANT CREATE ON SCHEMA contacts TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA contacts TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA contacts TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA contacts TO vault_ntrfyr_admin_role;

\echo '--- Granting ALL Privileges to existing schema: security ---'
GRANT USAGE ON SCHEMA security TO vault_ntrfyr_admin_role;
GRANT CREATE ON SCHEMA security TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA security TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA security TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA security TO vault_ntrfyr_admin_role;

\echo '--- Granting ALL Privileges to existing schema: public ---'
GRANT USAGE ON SCHEMA public TO vault_ntrfyr_admin_role;
GRANT CREATE ON SCHEMA public TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO vault_ntrfyr_admin_role;

\echo '--- Granting ALL Privileges to existing schema: links ---'
GRANT USAGE ON SCHEMA links TO vault_ntrfyr_admin_role;
GRANT CREATE ON SCHEMA links TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA links TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA links TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA links TO vault_ntrfyr_admin_role;

\echo '--- Granting ALL Privileges to existing schema: twilio ---'
GRANT USAGE ON SCHEMA twilio TO vault_ntrfyr_admin_role;
GRANT CREATE ON SCHEMA twilio TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA twilio TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA twilio TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA twilio TO vault_ntrfyr_admin_role;

\echo '--- Granting ALL Privileges to existing schema: emails ---'
GRANT USAGE ON SCHEMA emails TO vault_ntrfyr_admin_role;
GRANT CREATE ON SCHEMA emails TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA emails TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA emails TO vault_ntrfyr_admin_role;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA emails TO vault_ntrfyr_admin_role;


-- #######################################################################
-- # Section 2: Future-Proofing (ALTER DEFAULT PRIVILEGES)               #
-- # Ensures the temporary admin user can manage new objects created by  #
-- # the primary object-creating user (usually 'postgres').              #
-- #######################################################################

\echo '--- Setting Default Privileges for FUTURE objects (created by vault_ntrfyr_admin_role) ---'

-- Ensures any table/sequence/function created by a temporary admin user 
-- (which is a member of this role) automatically grants all necessary privileges back
-- to the same group.

-- #######################################################################
-- # Setting Default Privileges for FUTURE objects (Created by the       #
-- # Vault-generated temporary admin user)                               #
-- #######################################################################

-- Target Role: vault_ntrfyr_admin_role
-- Creator Role: The Vault-generated temporary admin user (who is a member of vault_ntrfyr_admin_role)
-- Goal: Ensure the privilege to manage newly created objects is automatically inherited by the group.

\echo '--- Setting Default Privileges for SCHEMA: public ---'
ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA public
    GRANT ALL ON TABLES TO vault_ntrfyr_admin_role;

ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA public
    GRANT ALL ON SEQUENCES TO vault_ntrfyr_admin_role;

ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA public
    GRANT ALL ON FUNCTIONS TO vault_ntrfyr_admin_role;

---

\echo '--- Setting Default Privileges for SCHEMA: contacts ---'
ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA contacts
    GRANT ALL ON TABLES TO vault_ntrfyr_admin_role;

ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA contacts
    GRANT ALL ON SEQUENCES TO vault_ntrfyr_admin_role;

ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA contacts
    GRANT ALL ON FUNCTIONS TO vault_ntrfyr_admin_role;

---

\echo '--- Setting Default Privileges for SCHEMA: security ---'
ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA security
    GRANT ALL ON TABLES TO vault_ntrfyr_admin_role;

ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA security
    GRANT ALL ON SEQUENCES TO vault_ntrfyr_admin_role;

ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA security
    GRANT ALL ON FUNCTIONS TO vault_ntrfyr_admin_role;

---

\echo '--- Setting Default Privileges for SCHEMA: links ---'
ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA links
    GRANT ALL ON TABLES TO vault_ntrfyr_admin_role;

ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA links
    GRANT ALL ON SEQUENCES TO vault_ntrfyr_admin_role;

ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA links
    GRANT ALL ON FUNCTIONS TO vault_ntrfyr_admin_role;

---

\echo '--- Setting Default Privileges for SCHEMA: twilio ---'
ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA twilio
    GRANT ALL ON TABLES TO vault_ntrfyr_admin_role;

ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA twilio
    GRANT ALL ON SEQUENCES TO vault_ntrfyr_admin_role;

ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA twilio
    GRANT ALL ON FUNCTIONS TO vault_ntrfyr_admin_role;

---

\echo '--- Setting Default Privileges for SCHEMA: emails ---'
ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA emails
    GRANT ALL ON TABLES TO vault_ntrfyr_admin_role;

ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA emails
    GRANT ALL ON SEQUENCES TO vault_ntrfyr_admin_role;

ALTER DEFAULT PRIVILEGES FOR ROLE vault_ntrfyr_admin_role IN SCHEMA emails
    GRANT ALL ON FUNCTIONS TO vault_ntrfyr_admin_role;


\echo '--- Default Privilege setup complete for all schemas. ---'

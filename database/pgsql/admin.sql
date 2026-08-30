CREATE SCHEMA IF NOT EXISTS bootstrap_admin;

SET search_path = bootstrap_admin;

CREATE OR REPLACE PROCEDURE bootstrap_admin.grant_app_role_privileges(
    p_role_name text,
    p_schemas text[]
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_schema text;
BEGIN
    FOREACH v_schema IN ARRAY p_schemas
    LOOP
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO %I', v_schema, p_role_name);

        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO %I', v_schema, p_role_name);

        EXECUTE format('GRANT EXECUTE ON ALL ROUTINES IN SCHEMA %I TO %I', v_schema, p_role_name);

        EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I', v_schema, p_role_name);

        EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT EXECUTE ON ROUTINES TO %I', v_schema, p_role_name);
    END LOOP;
END;
$$;

CREATE OR REPLACE PROCEDURE bootstrap_admin.grant_admin_role_privileges(
    p_role_name text,
    p_schemas text[]
)
LANGUAGE plpgsql
AS $$
DECLARE
    schema_name text;
BEGIN
    FOREACH schema_name IN ARRAY p_schemas
    LOOP
        EXECUTE format('GRANT ALL PRIVILEGES ON SCHEMA %I TO %I', schema_name, p_role_name);

        EXECUTE format('GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I TO %I', schema_name, p_role_name);

        EXECUTE format('GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA %I TO %I', schema_name, p_role_name);

        EXECUTE format('GRANT ALL PRIVILEGES ON ALL ROUTINES IN SCHEMA %I TO %I', schema_name, p_role_name);

        EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT ALL ON TABLES TO %I', schema_name, p_role_name);

        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA %I GRANT ALL ON SEQUENCES TO %I', schema_name, p_role_name);

        EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT ALL ON ROUTINES TO %I', schema_name, p_role_name);
    END LOOP;
END;
$$;
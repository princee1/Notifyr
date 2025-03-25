-- Active: 1740679093248@@127.0.0.1@5432@notifyr@security
SET search_path = security;

CREATE OR REPLACE FUNCTION secure_random_string(length INT) RETURNS TEXT AS $$
DECLARE
    raw_bytes BYTEA;
    encoded TEXT;
BEGIN
    raw_bytes := gen_random_bytes(length);
    encoded := encode(raw_bytes, 'base64');
    RETURN substring(encoded FROM 1 FOR length);
END;
$$ LANGUAGE plpgsql;

CREATE DOMAIN Scope AS VARCHAR(25) CHECK (
    VALUE IN ('SoloDolo', 'Organization')
);


CREATE DOMAIN ClientType AS VARCHAR(25) CHECK (
    VALUE IN ('User','Admin')
);

CREATE TABLE IF NOT EXISTS GroupClient (
    group_id UUID DEFAULT uuid_generate_v4 (),
    group_name VARCHAR(80) UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (group_id)
);

CREATE TABLE IF NOT EXISTS Client (
    client_id UUID DEFAULT uuid_generate_v4 (),
    client_name VARCHAR(200) UNIQUE,
    client_scope Scope DEFAULT 'SoloDolo',
    group_id UUID DEFAULT NULL,
    client_type ClientType DEFAULT 'User',
    issued_for VARCHAR(50) UNIQUE,
    authenticated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (client_id),
    FOREIGN KEY (group_id) REFERENCES GroupClient (group_id) ON DELETE SET NULL ON UPDATE CASCADE
    -- CHECK (SELECT COUNT(*) FROM Client WHERE client_type ='Admin') = 1
);

CREATE TABLE IF NOT EXISTS Challenge (
    client_id UUID ,
    challenge_auth TEXT UNIQUE DEFAULT secure_random_string(128),
    created_at_auth TIMESTAMPTZ DEFAULT NOW(),
    expired_at_auth TIMESTAMPTZ,
    challenge_refresh TEXT UNIQUE DEFAULT secure_random_string(256),
    created_at_refresh TIMESTAMPTZ DEFAULT NOW(),
    expired_at_refresh TIMESTAMPTZ ,
    PRIMARY KEY (client_id),
    FOREIGN KEY (client_id) REFERENCES Client (client_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS Blacklist (
    blacklist_id UUID DEFAULT uuid_generate_v4 (),
    client_id UUID UNIQUE DEFAULT NULL,
    group_id UUID UNIQUE DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expired_at TiMESTAMPTZ NOT NULL,
    PRIMARY KEY (blacklist_id),
    FOREIGN KEY (group_id) REFERENCES GroupClient (group_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (client_id) REFERENCES Client (client_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE OR REPLACE FUNCTION set_auth_challenge() RETURNS VOID AS $$
BEGIN
    SET search_path = security;

    UPDATE 
        Challenge
    SET 
        challenge_auth = secure_random_string(64),
        created_at_auth = NOW(),
        expired_at_auth = NOW() + (expired_at_auth - created_at_auth)
    WHERE 
        expired_at_auth <= NOW();
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION set_refresh_challenge() RETURNS VOID AS $$
BEGIN
    SET search_path = security;
    UPDATE 
        Challenge c
    SET 
        challenge_refresh = secure_random_string(128),
        authenticated = FALSE,
        created_at_refresh = NOW(),
        expired_at_refresh = NOW() + (expired_at_refresh - created_at_refresh)
    WHERE 
        expired_at_auth <= NOW();
END; $$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION raw_revoke_challenges(cid UUID) RETURNS VOID as $$
BEGIN
    SET search_path = security;
    UPDATE 
        Challenge c
    SET 
        challenge_auth = secure_random_string(64),
        expired_at_auth = NOW() + (expired_at_auth - created_at_auth),
        created_at_auth = NOW(),
        challenge_refresh = secure_random_string(128),
        expired_at_refresh = NOW() + (expired_at_refresh - created_at_refresh),
        created_at_refresh = NOW()
    
    WHERE
        c.client_id = cid;

END; $$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION raw_revoke_auth_token(cid UUID) RETURNS VOID as $$
BEGIN
    SET search_path = security;
    UPDATE 
        Challenge c
    SET 
        challenge_auth = secure_random_string(64),
        expired_at_auth = NOW() + (expired_at_auth - created_at_auth),
        created_at_auth = NOW()
    WHERE
        c.client_id = cid;

END; $$ LANGUAGE plpgsql;



CREATE OR REPLACE FUNCTION update_challenge() RETURNS VOID AS $$
BEGIN
    SET search_path = security;
    SELECT security.set_auth_challenge();
    SELECT security.set_refresh_challenge();
END; $$ LANGUAGE plpgsql;

SELECT cron.schedule (
    'update_challenge_hourly', '0 * * * *', 'SELECT security.update_challenge();'
    );

CREATE OR REPLACE FUNCTION delete_blacklist() RETURNS VOID AS $$
BEGIN
    SET search_path = security;
    DELETE FROM Blacklist
    WHERE expired_at <= NOW();
END; $$ LANGUAGE plpgsql;

SELECT cron.schedule (
        'delete_blacklist_hourly', '0 * * * *', 'SELECT security.delete_blacklist();'
        );

CREATE OR REPLACE FUNCTION compute_limit_group() RETURNS TRIGGER AS $compute_limit_group$
DECLARE
    group_count INT;

BEGIN
    SET 
        search_path = security;

    SELECT 
        COUNT(*) 
    INTO 
        group_count
    FROM 
        Groupclient;

    IF group_count >= 2 THEN
        RAISE NOTICE 'Group limit reached';
    RETURN NULL;
    ELSE 
        RETURN OLD;
    END IF;

END;
$compute_limit_group$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION compute_limit_client() RETURNS TRIGGER AS $compute_limit_client$
DECLARE
    client_count INT;

BEGIN   
    SET search_path = security;
    SELECT 
        COUNT(*) 
    INTO 
        client_count
    FROM 
        Client;

    IF client_count >= 10 THEN
        RAISE NOTICE 'Client limit reached';
    RETURN NULL;
    ELSE 
        RETURN OLD;
    END IF;

END;
$compute_limit_client$  LANGUAGE plpgsql;

CREATE TRIGGER limit_group
    BEFORE INSERT
    ON GroupClient
    FOR EACH ROW
    EXECUTE FUNCTION compute_limit_group();

CREATE TRIGGER limit_client
    BEFORE INSERT
    ON Client
    FOR EACH ROW
    EXECUTE FUNCTION compute_limit_client();


CREATE OR REPLACE FUNCTION guard_admin_creation() RETURNS TRIGGER AS $guard_admin_creation$
BEGIN
    SET search_path = security;
    IF NEW.client_type = 'Admin' THEN
        IF (SELECT COUNT(*) FROM Client WHERE client_type = 'Admin') > 0 THEN
            RAISE NOTICE 'Admin already exists';
            RETURN NULL;
        END IF;
    END IF;
    RETURN NEW;
END;
$guard_admin_creation$ LANGUAGE PLPGSQL

CREATE TRIGGER guard_admin_creation
    BEFORE INSERT OR UPDATE
    ON Client
    FOR EACH ROW
    EXECUTE FUNCTION guard_admin_creation();

CREATE OR REPLACE FUNCTION guard_admin_deletion() RETURNS TRIGGER AS $guard_admin_deletion$
BEGIN
    SET search_path = security;
    IF NEW.client_type = 'Admin' THEN
        RAISE NOTICE 'Admin cannot be deleted';
       RETURN NULL;  
    END IF;
    RETURN NEW;
END;
$guard_admin_deletion$ LANGUAGE PLPGSQL

CREATE TRIGGER guard_admin_deletion
    BEFORE DELETE OR UPDATE
    ON Client
    FOR EACH ROW
    EXECUTE FUNCTION guard_admin_deletion();
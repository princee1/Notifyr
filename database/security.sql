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
    VALUE IN ('User','Admin','Twilio')
);

CREATE TABLE IF NOT EXISTS GroupClient (
    group_id UUID DEFAULT uuid_generate_v1mc (),
    group_name VARCHAR(50) UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (group_id)
);

CREATE TABLE IF NOT EXISTS Client (
    client_id UUID DEFAULT uuid_generate_v1mc (),
    client_name VARCHAR(50) UNIQUE,
    client_scope Scope DEFAULT 'SoloDolo',
    group_id UUID DEFAULT NULL,
    client_type ClientType DEFAULT 'User',
    password TEXT DEFAULT NULL,
    password_salt TEXT DEFAULT NULL,
    can_login BOOLEAN DEFAULT NULL,
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
    challenge_auth VARCHAR(128) UNIQUE DEFAULT secure_random_string(128),
    created_at_auth TIMESTAMPTZ DEFAULT NOW(),
    expired_at_auth TIMESTAMPTZ,
    challenge_refresh VARCHAR(256) UNIQUE DEFAULT secure_random_string(256),
    created_at_refresh TIMESTAMPTZ DEFAULT NOW(),
    expired_at_refresh TIMESTAMPTZ ,
    last_authz_id UUID DEFAULT uuid_generate_v4 (),
    PRIMARY KEY (client_id),
    FOREIGN KEY (client_id) REFERENCES Client (client_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS Blacklist (
    blacklist_id UUID DEFAULT uuid_generate_v1mc (),
    client_id UUID UNIQUE DEFAULT NULL,
    group_id UUID UNIQUE DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expired_at TiMESTAMPTZ,
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
        -- authenticated = FALSE, TODO should i disconnect the client or nah?
        created_at_refresh = NOW(),
        expired_at_refresh = NOW() + (expired_at_refresh - created_at_refresh)
    WHERE 
        expired_at_refresh <= NOW();
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
    PERFORM set_auth_challenge();
    PERFORM set_refresh_challenge();
END; $$ LANGUAGE plpgsql;

SELECT cron.schedule (
    'update_challenge_every_5_minutes', '*/5 * * * *', 'SELECT security.update_challenge();'
    );

CREATE OR REPLACE FUNCTION delete_blacklist() RETURNS VOID AS $$
BEGIN
    SET search_path = security;
    DELETE FROM Blacklist
    WHERE expired_at <= NOW();

END; $$ LANGUAGE plpgsql;

SELECT cron.schedule (
    'delete_blacklist_every_5_minutes', '*/5 * * * *', 'SELECT security.delete_blacklist();'
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
        RAISE EXCEPTION 'Group limit reached';
    RETURN NULL;
    ELSE 
        RETURN NEW;
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

    IF client_count >= 11 THEN
        RAISE EXCEPTION 'Client limit reached';
    RETURN NULL;
    ELSE 
        RETURN NEW;
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
            RAISE EXCEPTION 'Admin already exists';
            RETURN NULL;
        END IF;
        RETURN NEW;
    END IF;
    RETURN NEW;
END;
$guard_admin_creation$ LANGUAGE PLPGSQL;

CREATE TRIGGER guard_admin_creation
    BEFORE INSERT
    ON Client
    FOR EACH ROW
    EXECUTE FUNCTION guard_admin_creation();

CREATE OR REPLACE FUNCTION guard_admin_deletion() RETURNS TRIGGER AS $guard_admin_deletion$
BEGIN
    SET search_path = security;
    IF OLD.client_type = 'Admin' THEN
        RAISE EXCEPTION 'Admin cannot be deleted or updated';
        RETURN NULL;  
    END IF;
    RETURN NEW;
END;
$guard_admin_deletion$ LANGUAGE plpgsql;

CREATE TRIGGER guard_admin_deletion
    BEFORE DELETE OR UPDATE
    ON Client
    FOR EACH ROW
    EXECUTE FUNCTION guard_admin_deletion();
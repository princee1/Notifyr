SET search_path = clients;

CREATE OR REPLACE FUNCTION secure_random_string(length INT) RETURNS TEXT AS $$
DECLARE
    raw_bytes BYTEA;
    encoded TEXT;
BEGIN
    raw_bytes := public.gen_random_bytes(length);
    encoded := encode(raw_bytes, 'base64');
    RETURN substring(encoded FROM 1 FOR length);
END;
$$ LANGUAGE plpgsql;

CREATE DOMAIN Role AS VARCHAR(15) CHECK (
    VALUE IN ('PUBLIC','ADMIN','RELAY','CUSTOM','MFA_OTP','CHAT','RESULT','STATIC','REFRESH','CONTACTS','TWILIO','SUBSCRIPTION','CLIENT','LINK','PROFILE',
    'ASSETS'
)
);

CREATE DOMAIN AuthType AS VARCHAR(15) CHECK(
    VALUE IN ('ACCESS_TOKEN','API_TOKEN')
);

CREATE DOMAIN Scope AS VARCHAR(15) CHECK (
    VALUE IN ('SoloDolo', 'Organization','Domain','Free')
);

CREATE DOMAIN ClientType AS VARCHAR(10) CHECK (
    VALUE IN ('User','Admin','Twilio','App','Service')
);

CREATE TABLE IF NOT EXISTS GroupClient (
    group_id UUID DEFAULT public.uuid_generate_v1mc (),
    group_name VARCHAR(50) UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (group_id)
);

CREATE TABLE IF NOT EXISTS Client (
    client_id UUID DEFAULT public.uuid_generate_v1mc (),
    client_name VARCHAR(50) UNIQUE,
    client_email VARCHAR(200) UNIQUE,
    client_description TEXT DEFAULT NULL,
    client_username VARCHAR(30) UNIQUE DEFAULT 'notifyr-user-' || secure_random_string(12),
    client_scope Scope DEFAULT 'SoloDolo',
    client_type ClientType DEFAULT 'User',
    group_id UUID DEFAULT NULL,
    authenticated BOOLEAN DEFAULT FALSE,
    -- max_connection INT DEFAULT 1,
    -- current_connection_count INT DEFAULT 0,
    issued_for VARCHAR(50) UNIQUE DEFAULT secure_random_string(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (client_id),
    FOREIGN KEY (group_id) REFERENCES GroupClient (group_id) ON DELETE SET NULL ON UPDATE CASCADE
    -- CHECK (SELECT COUNT(*) FROM Client WHERE client_type ='Admin') = 1
);

CREATE TABLE IF NOT EXISTS PolicyMapping(
    mapping_id UUID DEFAULT public.uuid_generate_v1mc(),
    policy_id VARCHAR(30),
    client_id UUID DEFAULT NULL,
    group_id UUID DEFAULT NULL,
    PRIMARY KEY (mapping_id),
    CONSTRAINT client_xor_group CHECK (
        (client_id IS NOT NULL AND group_id IS NULL) OR
        (client_id IS NULL AND group_id IS NOT NULL)
    ),
    FOREIGN KEY (group_id) REFERENCES GroupClient (group_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (client_id) REFERENCES Client (client_id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Unique for policy_id + client_id where client_id is not null
CREATE UNIQUE INDEX IF NOT EXISTS unique_policy_client
ON PolicyMapping(policy_id, client_id)
WHERE client_id IS NOT NULL;

-- Unique for policy_id + group_id where group_id is not null
CREATE UNIQUE INDEX IF NOT EXISTS unique_policy_group
ON PolicyMapping(policy_id, group_id)
WHERE group_id IS NOT NULL;

-- ------------------------------------             -------------------------------------------#
-- ------------------------------------             -------------------------------------------#

CREATE OR REPLACE FUNCTION compute_limit_group() RETURNS TRIGGER AS $compute_limit_group$
DECLARE
    group_count INT;

BEGIN
    SET 
        search_path = clients;

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
    SET search_path = clients;
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

-- ------------------------------------             -------------------------------------------#

-- ------------------------------------             -------------------------------------------#

CREATE OR REPLACE FUNCTION guard_admin_creation() RETURNS TRIGGER AS $guard_admin_creation$
BEGIN
    SET search_path = clients;
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
    SET search_path = clients;
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

-- ------------------------------------             -------------------------------------------#

-- ------------------------------------             -------------------------------------------#

DELETE FROM clients.Client;

DELETE FROM clients.Groupclient;

-- Active: 1740679093248@@127.0.0.1@5432@notifyr@contacts
DROP SCHEMA IF EXISTS contacts CASCADE;

CREATE SCHEMA contacts;

SET search_path = contacts;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE DOMAIN Lang AS VARCHAR(15) CHECK (VALUE IN ('fr', 'en'))

CREATE DOMAIN SubscriptionStatus AS VARCHAR(20) CHECK (
    VALUE IN ('Active', 'Inactive')
)

CREATE DOMAIN Status AS VARCHAR(20) CHECK (
    VALUE IN (
        'Active',
        'Pending',
        'Blacklist',
        'Inactive'
    )
)

CREATE DOMAIN Frequency AS VARCHAR(20) CHECK (
    VALUE IN (
        'weekly',
        'bi_weekly',
        'monthly',
        'always'
    )
)

CREATE DOMAIN ContentType AS VARCHAR(30) CHECK (
    VALUE IN (
        'newsletter',
        'event',
        'notification', -- user can receive by default
        'promotion',
        'update', -- user can receive by default
        'other'
    )
)

CREATE TABLE IF NOT EXISTS Contact (
    contact_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(50) UNIQUE NOT NULL,
    phone VARCHAR(50) UNIQUE,
    status Status DEFAULT 'Pending',
    app_registered BOOLEAN DEFAULT FALSE,
    opt_in_code INT UNIQUE,
    lang Lang DEFAULT 'en',
    frequency Frequency DEFAULT 'always',
    action_code TEXT UNIQUE,
    auth_token TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_opt_in_code CHECK (opt_in_code >= 100000 AND opt_in_code <= 999999)
)

CREATE TABLE IF NOT EXISTS SecurityContact (
    security_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contact_id UUID,
    security_code TEXT DEFAULT NULL,
    security_code_salt VARCHAR(64) DEFAULT NULL,
    security_phrase TEXT DEFAULT NULL,
    security_phrase_salt VARCHAR(64) DEFAULT NULL,
    voice_embedding TEXT DEFAULT NULL,
    voice_embedding_salt VARCHAR(64) DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (contact_id) REFERENCES Contact (contact_id) ON DELETE CASCADE ON UPDATE CASCADE
)

CREATE TABLE IF NOT EXISTS SubscriptionContact (
    subscription_id UUID DEFAULT uuid_generate_v4(),
    contact_id UUID UNIQUE,
    email_status SubscriptionStatus NOT NULL,
    sms_status SubscriptionStatus NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (subscription_id),
    FOREIGN KEY (contact_id) REFERENCES Contact (contact_id) ON DELETE CASCADE ON UPDATE CASCADE
)

CREATE TABLE IF NOT EXISTS Reason (
    reason_id UUID DEFAULT uuid_generate_v4(),
    reason_description TEXT DEFAULT NULL,
    reason_name UNIQUE TEXT,
    reason_count BIGINT DEFAULT 0,
    PRIMARY KEY (reason_id)
)

CREATE TABLE IF NOT EXISTS SubsContent (
    content_id UUID DEFAULT uuid_generate_v4(),
    content_name UNIQUE VARCHAR(50),
    content_description TEXT DEFAULT NULL,
    content_type ContentType DEFAULT 'other'
    PRIMARY KEY (content_id)
)

CREATE TABLE IF NOT EXISTS Subscription (
    subs_id UUID UNIQUE DEFAULT uuid_generate_v4(),
    contact_id UUID,
    content_id UUID,
    subs_status SubscriptionStatus DEFAULT 'Active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (
        subs_id,
        contact_id,
        content_id
    ) FOREIGN KEY (contact_id) REFERENCES Contact (contact_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (content_id) REFERENCES SubsContent (content_id) ON DELETE CASCADE ON UPDATE CASCADE
)


CREATE OR REPLACE FUNCTION update_reason(VARCHAR(50)) RETURNS VOID AS $$ BEGIN
RETURN QUERY

SELECT pg_advisory_xact_lock(hashtext($1));
INSERT INTO 
    contacts.Reason (reason_name, reason_count)
VALUES ($1, 1)
ON CONFLICT (reason) DO
UPDATE contacts.Reason
SET 
    reason_count = reason_count + 1
WHERE 
    reason_name = $1;
END;

% % LANGUAGE PLPGSQL SECURITY DEFINER ;



CREATE OR REPLACE FUNCTION reset_reason(VARCHAR(50)) RETURNS VOID AS $$ BEGIN
RETURN QUERY

SELECT pg_advisory_xact_lock(hashtext ($1));

INSERT INTO
    contacts.Reason (reason_name, reason_count)
VALUES ($1, 0)
ON CONFLICT (reason) DO
UPDATE contacts.Reason
SET
    contacts.reason_count = 0
WHERE
    contacts.reason_name = $1;

END;

% % LANGUAGE PLPGSQL SECURITY DEFINER ;


-- CREATE OR REPLACE FUNCTION check_user_status(UUID,VARCHAR(50)) RETURNS BOOlEAN AS $$ BEGIN
-- RETURN QUERY

-- END;





-- users Views
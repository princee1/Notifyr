-- Active: 1740679093248@@127.0.0.1@5432@notifyr@contacts
DROP SCHEMA IF EXISTS contacts CASCADE;

CREATE SCHEMA contacts;

SET search_path = contacts;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE EXTENSION IF NOT EXISTS pg_cron;

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
    contact_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(50) UNIQUE NOT NULL,
    phone VARCHAR(50) UNIQUE,
    status Status DEFAULT 'Pending',
    app_registered BOOLEAN DEFAULT FALSE,
    opt_in_code INT UNIQUE, -- double opt in code
    lang Lang DEFAULT 'en',
    frequency Frequency DEFAULT 'always',
    action_code TEXT UNIQUE DEFAULT NULL, -- unsubscribe/subscribe
    auth_token TEXT UNIQUE DEFAULT NULL, --NONCE
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_opt_in_code CHECK (
        opt_in_code >= 10000000000000
        AND opt_in_code <= 99999999999999
    )
)

CREATE TABLE IF NOT EXISTS SecurityContact (
    security_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
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

-- TODO Combine the SubscriptionContact and Content Type Later ...
CREATE TABLE IF NOT EXISTS SubscriptionContact (
    subscription_id UUID DEFAULT uuid_generate_v4 (),
    contact_id UUID UNIQUE,
    email_status SubscriptionStatus NOT NULL,
    sms_status SubscriptionStatus NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (subscription_id),
    FOREIGN KEY (contact_id) REFERENCES Contact (contact_id) ON DELETE CASCADE ON UPDATE CASCADE
)

CREATE TABLE IF NOT EXISTS ContentTypeSubscription (
    contact_id UUID UNIQUE,
    newsletter BOOLEAN DEFAULT FALSE,
    event BOOLEAN DEFAULT FALSE,
    -- notification BOOLEAN DEFAULT TRUE, -- user can receive by default
    promotion BOOLEAN DEFAULT FALSE,
    -- update BOOLEAN DEFAULT TRUE, -- user can receive by default
    other BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (contact_id),
    FOREIGN KEY (contact_id) REFERENCES Contact (contact_id) ON DELETE CASCADE ON UPDATE CASCADE
)

CREATE TABLE IF NOT EXISTS Reason (
    reason_id UUID DEFAULT uuid_generate_v4 (),
    reason_description TEXT DEFAULT NULL,
    reason_name VARCHAR(50) UNIQUE,
    reason_count BIGINT DEFAULT 0,
);

DELETE * FROM Reason;

INSERT INTO
    Reason (
        reason_name,
        reason_description
    )
VALUES (
        'Not Interested',
        'The user is not interested in the content.'
    ),
    (
        'Too Many Emails',
        'The user is receiving too many emails.'
    ),
    (
        'Content Not Relevant',
        'The content is not relevant to the user.'
    ),
    (
        'Other',
        'Other reasons for unsubscribing.'
    ),
    (
        'Switched to Competitor',
        'The user has switched to a competitor.'
    ),
    (
        'Privacy Concerns',
        'The user has concerns about privacy.'
    ),
    (
        'Technical Issues',
        'The user is experiencing technical issues.'
    ),
    (
        'No Longer Needed',
        'The user no longer needs the service.'
    );

CREATE TABLE IF NOT EXISTS SubsContent (
    content_id UUID DEFAULT uuid_generate_v4 (),
    content_name VARCHAR(50) UNIQUE,
    content_description TEXT DEFAULT NULL,
    content_type ContentType DEFAULT 'other',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (content_id)
)

ALTER TABLE Subscontent ADD COLUMN ttl TIMESTAMP;

CREATE TABLE IF NOT EXISTS Subscription (
    subs_id UUID UNIQUE DEFAULT uuid_generate_v4 (),
    contact_id UUID,
    content_id UUID,
    subs_status SubscriptionStatus DEFAULT 'Active',
    preferred_method VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (contact_id, content_id),
    FOREIGN KEY (contact_id) REFERENCES Contact (contact_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (content_id) REFERENCES SubsContent (content_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT preferred_method CHECK (
        preferred_method IN ('email', 'sms')
    )
)

CREATE OR REPLACE FUNCTION delete_subscriptions_by_contact(contact_id UUID) RETURNS VOID AS $$
BEGIN
    DELETE FROM Subscription S
    WHERE S.contact_id = contact_id AND S.content_id NOT IN (
        SELECT T.content_id FROM Subscription AS T
        NATURAL JOIN SubsContent C WHERE C.content_type='notification' OR C.content_type='update'
    );
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_reason(reason_name VARCHAR(50)) RETURNS VOID AS $$
BEGIN

PERFORM pg_advisory_xact_lock(hashtext(reason_name));
INSERT INTO 
    contacts.Reason (reason_name, reason_count)
VALUES (reason_name, 1)
ON CONFLICT (reason_name) DO
UPDATE
SET 
    reason_count = contacts.Reason.reason_count + 1
WHERE 
    contacts.Reason.reason_name = reason_name;

END; $$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION reset_reason(reason_name VARCHAR(50)) RETURNS VOID AS $$
BEGIN

PERFORM pg_advisory_xact_lock(hashtext(reason_name));

INSERT INTO
    contacts.Reason (reason_name, reason_count)
VALUES (reason_name, 0)
ON CONFLICT (reason_name) DO
UPDATE
SET
    reason_count = 0
WHERE
    contacts.Reason.reason_name = reason_name;

END; $$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE VIEW UserSummary AS
SELECT
    c.contact_id,
    c.first_name,
    c.last_name,
    c.email,
    c.phone,
    c.status,
    c.app_registered,
    c.lang,
    c.frequency,
    c.created_at,
    c.updated_at,
    COALESCE(
        sc.security_code IS NOT NULL,
        FALSE
    ) AS has_security_code,
    COALESCE(
        sc.security_phrase IS NOT NULL,
        FALSE
    ) AS has_security_phrase,
    COALESCE(
        sc.voice_embedding IS NOT NULL,
        FALSE
    ) AS has_voice_embedding,
    COALESCE(s.email_status, 'Inactive') AS email_status,
    COALESCE(s.sms_status, 'Inactive') AS sms_status,
    COUNT(subs.content_id) AS subscription_count,
    cts.newsletter,
    cts.promotion,
    cts.event,
    cts.other,
    cts.update_at AS content_type_subs_updated_at
FROM
    Contact c
    LEFT JOIN SecurityContact sc ON c.contact_id = sc.contact_id
    LEFT JOIN SubscriptionContact s ON c.contact_id = s.contact_id
    LEFT JOIN Subscription subs ON c.contact_id = subs.contact_id
    LEFT JOIN SubsContent sub_content ON subs.content_id = sub_content.content_id
    LEFT JOIN ContentTypeSubscription cts  ON cts.contact_id = c.contact_id
GROUP BY
    sub_content.content_id,
    sc.security_code,
    sc.security_phrase,
    sc.voice_embedding,
    s.email_status,
    s.sms_status,
    c.contact_id;

CREATE OR REPLACE FUNCTION delete_expired_subscontent() RETURNS VOID AS $$
BEGIN
    DELETE FROM SubsContent WHERE ttl != NULL and ttl < NOW();
END;
$$ LANGUAGE plpgsql;

SELECT cron.schedule('delete_expired_subscontent', '0 0 * * *', $$CALL delete_expired_subscontent();$$);

-- NOTE or create a schedule for each row using a Trigger
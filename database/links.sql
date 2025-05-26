-- Active: 1740679093248@@localhost@5432@notifyr@links
SET search_path = links;


CREATE TABLE IF NOT EXISTS Link (
    link_id UUID DEFAULT uuid_generate_v1mc(),
    link_name VARCHAR(100) UNIQUE,
    link_short_id VARCHAR(7) UNIQUE,
    link_url VARCHAR(150) UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expiration TIMESTAMPTZ DEFAULT NULL,
    expiration_verification TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '1 week'),
    total_visit_count INT DEFAULT 0,
    converted_count INT DEFAULT NULL,
    total_session_count INT DEFAULT NULL,
    public BOOLEAN DEFAULT TRUE,
    -- ownership_public_key TEXT DEFAULT NULL,
    -- ownership_private_key TEXT DEFAULT NULL,
    ownership_signature TEXT DEFAULT NULL,
    ownership_nonce VARCHAR(50) DEFAULT NULL,
    verified BOOLEAN DEFAULT FALSE,
    archived BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (link_id)
);

CREATE TABLE IF NOT EXISTS LinkEvent (
    event_id UUID DEFAULT uuid_generate_v1mc(),
    link_id UUID,
    link_path VARCHAR(100) DEFAULT '/',
    contact_id UUID DEFAULT NULL,
    email_id UUID DEFAULT NULL,
    user_agent VARCHAR(150) DEFAULT NULL,
    --ip_address VARCHAR(50),
    geo_lat FLOAT DEFAULT NULL,
    geo_long FLOAT DEFAULT NULL,
    country VARCHAR(5),
    region VARCHAR(60),
    referrer VARCHAR(100),
    timezone VARCHAR(80),
    city VARCHAR(100),
    date_clicked TIMESTAMPTZ DEFAULT NOW(),
    expiring_date TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '2 week'),
    PRIMARY KEY (event_id),
    FOREIGN KEY (link_id) REFERENCES Link(link_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (contact_id) REFERENCES contacts.Contact(contact_id) ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (email_id) REFERENCES emails.EmailTracking(email_id) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS LinkSession (
    session_id UUID DEFAULT uuid_generate_v1mc(),
    contact_id UUID DEFAULT NULL,
    link_id UUID NOT NULL,
    converted BOOLEAN DEFAULT FALSE,
    expiring_date TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '2 week'),
    PRIMARY KEY (session_id),
    FOREIGN KEY (link_id) REFERENCES Link(link_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (contact_id) REFERENCES contacts.Contact(contact_id) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS LinkAnalytics(
    link_id UUID NOT NULL,
    week_start_date DATE NOT NULL DEFAULT DATE_TRUNC('week', NOW()),
    country VARCHAR(5),
    region VARCHAR(60),
    -- referrer VARCHAR(100),
    city VARCHAR(100),
    device public.DeviceType DEFAULT 'unknown',
    visits_counts INT DEFAULT 1,
    PRIMARY KEY (link_id,country,region,city,device),
    FOREIGN KEY (link_id) REFERENCES Link(link_id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TYPE analytics_input AS (
    link_id UUID,  
    country VARCHAR(5),
    region VARCHAR(60),
    -- referrer VARCHAR(100),
    city VARCHAR(100),
    device public.DeviceType,
    visits_counts INT
);

CREATE TYPE links_vc_input AS (
    link_id UUID,
    visits_counts INT
);

CREATE OR REPLACE FUNCTION bulk_upsert_links_visits_counts(data links.links_vc_input[])  RETURNS VOID AS $$
DECLARE
    record links.links_vc_input;

BEGIN
    SET search_path = links;

    FOREACH record IN ARRAY data
    LOOP
        INSERT INTO Link (link_id, total_visit_count)
        VALUES 
            (record.link_id, record.visits_counts)
        ON CONFLICT (link_id)
        DO UPDATE
            SET total_visit_count = Link.total_visit_count + EXCLUDED.total_visit_count;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION bulk_upsert_analytics(data links.analytics_input[]) RETURNS VOID AS $$
DECLARE
    record links.analytics_input;
BEGIN
    SET search_path = links;

    FOREACH record IN ARRAY data
    LOOP
        INSERT 
            INTO LinkAnalytics (link_id,week_start_date, country, region, city, device, visits_counts )
        VALUES 
            (record.link_id,DATE_TRUNC('week', NOW()), record.country, record.region, record.city, record.device, record.visits_counts)
        ON CONFLICT 
            (link_id,week_start_date, country, region, city, device, week_start_date)
        DO UPDATE 
            SET visits_counts = LinkAnalytics.visits_counts + EXCLUDED.visits_counts;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION delete_expired_links() RETURNS VOID AS $$
BEGIN
    SET search_path = links;
    DELETE FROM Link
    WHERE expiration <= NOW()
    OR 
        expiration_verification <= NOW ();
END;
$$ LANGUAGE PLPGSQL;

CREATE OR REPLACE FUNCTION delete_link_event_session() RETURNS VOID AS $$
BEGIN
    SET search_path = links;
    DELETE FROM 
        LinkEvent
    WHERE
        expiring_date <= NOW();

    DELETE FROM 
        LinkSession
    WHERE
        expiring_date <= NOW();
END;
$$ LANGUAGE PLPGSQL;


SELECT cron.schedule('delete_expired_links_every_day', '0 0 * * *', 'SELECT links.delete_expired_links();');

SELECT cron.schedule('delete_expired_link_session_event_every_day', '0 0 * * *', 'SELECT links.delete_link_event_session();');

CREATE OR REPLACE FUNCTION compute_limit() RETURNS TRIGGER AS $compute_limit$
DECLARE
    links_count INT;
    public_links_count INT;

BEGIN
SET search_path = links;
SELECT 
    COUNT(*) 
INTO 
    links_count 
FROM 
    Link;

SELECT
    COUNT(*)
INTO
    public_links_count
FROM 
    Link
WHERE
    public =True;

IF public_links_count >=9 THEN
    RAISE EXCEPTION 'Public Links Limit Reached';
    RETURN OLD;
ELSE
    RETURN NEW;
END IF;

IF links_count >= 15 THEN
    RAISE EXCEPTION 'Links Limit Reached';
    RETURN OLD;
ELSE
    RETURN NEW;
END IF;
END;
$compute_limit$ LANGUAGE plpgsql;

CREATE TRIGGER limit_links
BEFORE INSERT ON Link
FOR EACH ROW
EXECUTE FUNCTION compute_limit();
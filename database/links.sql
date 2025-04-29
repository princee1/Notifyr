SET search_path = links;


CREATE TABLE IF NOT EXISTS Link (
    link_id UUID DEFAULT uuid_generate_v1mc(),
    link_name VARCHAR(100) UNIQUE NOT NULL,
    link_short_id VARCHAR(20) UNIQUE NOT NULL,
    link_url VARCHAR(150) UNIQUE NOT NULL,
    expiration TIMESTAMPTZ DEFAULT NULL,
    expiration_verification TIMESTAMPTZ DEFAULT NOW() + "1 week"
    total_visit_count INT DEFAULT 0,
    public BOOLEAN DEFAULT TRUE,
    verified BOOLEAN DEFAULT FALSE,
    archived BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (link_id)
);

CREATE TABLE IF NOT EXISTS LinkEvent (
    event_id UUID DEFAULT uuid_generate_v1mc(),
    link_id UUID NOT NULL,
    link_path VARCHAR(100) DEFAULT "/",
    contact_id UUID DEFAULT NULL,
    email_id UUID DEFAULT NULL,
    user_agent VARCHAR(150) DEFAULT NULL,
    ip_address VARCHAR(50),
    geo_lat FLOAT DEFAULT NULL,
    geo_long FLOAT DEFAULT NULL,
    country VARCHAR(60),
    city VARCHAR(100),
    date_clicked TIMESTAMPTZ DEFAULT NOW(),
    expiring_date TIMESTAMPTZ,
    PRIMARY KEY (event_id),
    FOREIGN KEY (link_id) REFERENCES Link(link_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (contact_id) REFERENCES contacts.Contact(contact_id) ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (email_id) REFERENCES emails.EmailTracking(email_id) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS LinkSession (
    session_id UUID DEFAULT uuid_generate_v1mc(),
    contact_id UUID DEFAULT NULL,
    link_id UUID NOT NULL,
    converted BOOLEAN DEFAULT NULL,
    PRIMARY KEY (session_id),
    FOREIGN KEY (link_id) REFERENCES Link(link_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (contact_id) REFERENCES contacts.Contact(contact_id) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE OR REPLACE FUNCTION delete_expired_links() RETURNS VOID AS $$
BEGIN
    SET search_path = links;
    DELETE FROM Link
    WHERE expiration <= NOW()
    OR 
        expiration_validation <= NOW ();
END;
$$ LANGUAGE PLPGSQL;

SELECT cron.schedule('delete_expired_links_every_day', '0 0 * * *', 'SELECT links.delete_expired_links();');


CREATE OR REPLACE FUNCTION compute_limit() RETURNS TRIGGER AS $compute_limit$
DECLARE
    links_count INT;

BEGIN
SET search_path = links;
SELECT 
    COUNT(*) 
INTO 
    links_count 
FROM 
    Link;

IF links_count >= 15 THEN
    RAISE EXCEPTION 'Links Limit Reached';
    RETURN OLD;
ELSE
    RETURN NEW;
END IF;
END;
$compute_limit$ LANGUAGE plpgsql;



CREATE TRIGGER links_contact
BEFORE INSERT ON Link
FOR EACH ROW
EXECUTE FUNCTION compute_limit();
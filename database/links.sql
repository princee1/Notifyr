SET search_path = links;


CREATE TABLE IF NOT EXISTS Link (
    link_id UUID DEFAULT uuid_generate_v1mc(),
    link_name VARCHAR(100),
    link_url VARCHAR(150),
    total_visit_count INT DEFAULT 0,
)

CREATE TABLE IF NOT EXISTS VisitEvents(
    event_id UUID DEFAULT uuid_generate_v1mc(),
    link_id UUID NOT NULL,
    contact_id UUID DEFAULT NULL,
    ip_address VARCHAR(50),
    geo_lat FLOAT DEFAULT NULL,
    geo_long FLOAT DEFAULT NULL,
    country VARCHAR(60),
    city VARCHAR(100,)
    date_cliCked TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (event_id),
    Foreign Key (contact_id) REFERENCES contacts.Contact(contact_id) ON UPDATE CASCADE ON DELETE SET NULL
)
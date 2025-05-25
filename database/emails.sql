-- Active: 1740679093248@@localhost@5432@notifyr@emails
SET search_path = emails;

CREATE DOMAIN EmailStatus AS VARCHAR(50) CHECK (
    VALUE IN (
        'RECEIVED',
        'SENT',
        'DELIVERED',
        'SOFT-BOUNCE',
        'HARD-BOUNCE',
        'MAILBOX-FULL',
        'OPENED',
        'LINK-CLICKED',
        'FAILED',
        'BLOCKED',
        'COMPLAINT',
        'DEFERRED',
        'DELAYED'
        'REPLIED',
        'MAILBOX-UNREACHABLE',
        'USER-NOT-FOUND',
    )
);

CREATE TABLE IF NOT EXISTS EmailTracking (
    email_id UUID DEFAULT uuid_generate_v1mc (),
    message_id VARCHAR(150) UNIQUE NOT NULL,
    recipient VARCHAR(100) NOT NULL,
    esp_provider VARCHAR(30) DEFAULT NULL,
    date_sent TIMESTAMPTZ DEFAULT NOW(),
    last_update TIMESTAMPTZ DEFAULT NOW(),
    expired_tracking_date TIMESTAMPTZ,
    email_current_status EmailStatus,
    subject VARCHAR(150),
    spam_label VARCHAR(50),
    spam_detection_confidence FLOAT,
    PRIMARY KEY (email_id)
);

CREATE TABLE IF NOT EXISTS TrackingEvent (
    event_id UUID DEFAULT uuid_generate_v1mc (),
    email_id UUID NOT NULL,
    contact_id UUID DEFAULT NULL,
    current_event EmailStatus NOT NULL,
    description VARCHAR(200) DEFAULT NULL,
    date_event_received TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (event_id),
    FOREIGN KEY (email_id) REFERENCES EmailTracking (email_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (contact_id) REFERENCES contacts.Contact(contact_id) ON UPDATE CASCADE ON DELETE NO ACTION
);

CREATE TABLE IF NOT EXISTS TrackedLinks (
    -- Define columns here as needed
);


CREATE TABLE IF NOT EXISTS EmailAnalytics (
    
);


CREATE OR REPLACE FUNCTION delete_expired_email_tracking() RETURNS VOID AS $$
BEGIN
    SET search_path = emails;

    DELETE FROM EmailTracking
    WHERE expired_tracking_date <= NOW();
END;
$$ LANGUAGE PLPGSQL;


CREATE OR REPLACE FUNCTION delete_non_mapped_email_event() RETURNS VOID AS $$
BEGIN
    SET search_path = emails;
    DELETE FROM 
        TrackingEvent te 
    WHERE
        te.email_id NOT IN (
            SELECT e.email_id FROM EmailTracking
        ) 
    OR 
        te.email_id == NULL;

END;
$$ LANGUAGE PLPGSQL;

CREATE OR REPLACE FUNCTION set_email_delivered() RETURNS VOID AS $$
BEGIN
    SET search_path = emails;

    UPDATE EmailTracking e
    SET email_current_status = 'DELIVERED'
    WHERE email_current_status = 'SEN' AND NOW() - date_sent >= INTERVAL '5 hours';
END;
$$ LANGUAGE PLPGSQL;

-- Schedule the function to run every hour using pg_cron
SELECT cron.schedule (
        'set_email_delivered_every_hour', -- Job name
        '0 * * * *', -- Cron expression for every hour
        'SELECT emails.set_email_delivered();'
            );

SELECT cron.schedule (
                'delete_expired_email_tracking_every_day',
                '0 0 * * *', -- Cron expression for every day at midnight
                'SELECT emails.delete_expired_email_tracking();'
            );

SELECT cron.schedule (
                'delete_non_mapped_email_event_every_day',
                '0 */3 * * *', -- Cron expression for every 3 hours
                'SELECT emails.delete_non_mapped_email_event();'
            );

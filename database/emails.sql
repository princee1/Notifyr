SET search_path = emails;

CREATE DOMAIN EmailStatus AS VARCHAR(50) CHECK (
    VALUE IN (
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
    )
);

CREATE TABLE IF NOT EXISTS EmailTracking (
    email_id UUID DEFAULT uuid_generate_v1mc (),
    message_id VARCHAR(150) UNIQUE NOT NULL,
    recipient VARCHAR(100) NOT NULL,
    date_sent TIMESTAMPTZ DEFAULT NOW(),
    last_update TIMESTAMPTZ DEFAULT NOW(),
    expired_tracking_date TIMESTAMPTZ,
    email_current_status EmailStatus,
    spam_label VARCHAR(50),
    spam_detection_confidence FLOAT,
    PRIMARY KEY (email_id)
);

CREATE TABLE IF NOT EXISTS TrackingEvent (
    event_id UUID DEFAULT uuid_generate_v1mc (),
    email_id UUID NOT NULL,
    current_event EmailStatus NOT NULL,
    date_event_received TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (event_id),
    FOREIGN KEY (email_id) REFERENCES EmailTracking (email_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS TrackedLinks (
    -- Define columns here as needed
);


CREATE OR REPLACE FUNCTION delete_expired_email_tracking() RETURNS VOID AS $$
BEGIN
    SET search_path = emails;

    DELETE FROM EmailTracking e
    WHERE e.expired_tracking_date <= NOW();
END;
$$ LANGUAGE PLPGSQL;

CREATE OR REPLACE FUNCTION set_email_delivered() RETURNS VOID AS $$
BEGIN
    SET search_path = emails;

    UPDATE EmailTracking e
    SET e.email_current_status = 'DELIVERED'
    WHERE e.email_current_status = 'SENT' AND NOW() - e.date_sent >= INTERVAL '5 hours';
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
            )

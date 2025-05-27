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
        'DELAYED',
        'REPLIED'
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
    event_id UUID DEFAULT uuid_generate_v1mc(),
    email_id UUID NOT NULL,
    contact_id UUID DEFAULT NULL,
    current_event EmailStatus NOT NULL,
    description VARCHAR(200) DEFAULT NULL,
    date_event_received TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (event_id),
    FOREIGN KEY (email_id) REFERENCES EmailTracking(email_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (contact_id) REFERENCES contacts.Contact(contact_id) ON UPDATE CASCADE ON DELETE NO ACTION
);

CREATE TABLE IF NOT EXISTS TrackedLinks (
    -- Define columns here as needed
);

-- Create EmailAnalytics table
CREATE TABLE IF NOT EXISTS EmailAnalytics (
    analytics_id UUID DEFAULT uuid_generate_v1mc (),
    -- esp_provider VARCHAR(30),
    week_start_date DATE NOT NULL DEFAULT DATE_TRUNC('week', NOW()),
    emails_sent INT DEFAULT 0,
    emails_delivered INT DEFAULT 0,
    emails_opened INT DEFAULT 0,
    emails_bounced INT DEFAULT 0,
    emails_replied INT DEFAULT 0,
    PRIMARY KEY (analytics_id),
    -- UNIQUE(week_start_date,esp_provider)
    UNIQUE (week_start_date)
);

-- Function to upsert the latest EmailAnalytics row
CREATE OR REPLACE FUNCTION upsert_email_analytics(
    sent_count INT,
    delivered_count INT,
    opened_count INT,
    bounced_count INT,
    replied_count INT
) RETURNS VOID AS $$
BEGIN
    SET search_path = emails;

    INSERT INTO EmailAnalytics (week_start_date, emails_sent, emails_delivered, emails_opened, emails_bounced, emails_replied)
    VALUES (DEFAULT, sent_count, delivered_count, opened_count, bounced_count, replied_count)
    ON CONFLICT (week_start_date)
    DO UPDATE SET
        emails_sent = EmailAnalytics.emails_sent + EXCLUDED.emails_sent,
        emails_delivered = EmailAnalytics.emails_delivered + EXCLUDED.emails_delivered,
        emails_opened = EmailAnalytics.emails_opened + EXCLUDED.emails_opened,
        emails_bounced = EmailAnalytics.emails_bounced + EXCLUDED.emails_bounced,
        emails_replied = EmailAnalytics.emails_replied + EXCLUDED.emails_replied;
END;
$$ LANGUAGE PLPGSQL;

-- Function to aggregate email analytics dynamically based on grouping
CREATE OR REPLACE FUNCTION calculate_email_analytics_grouped(
    group_by_factor INT
) RETURNS TABLE (
    group_number INT,
    emails_sent INT,
    emails_delivered INT,
    emails_opened INT,
    emails_bounced INT,
    emails_replied INT
) AS $$
BEGIN
    RETURN QUERY
    SET search_path = emails;

    SELECT
        FLOOR(EXTRACT(EPOCH FROM (week_start_date - MIN(week_start_date) OVER ())) / (group_by_factor * 7 * 24 * 60 * 60)) + 1 AS group_number,
        SUM(emails_sent) AS emails_sent,
        SUM(emails_delivered) AS emails_delivered,
        SUM(emails_opened) AS emails_opened,
        SUM(emails_bounced) AS emails_bounced,
        SUM(emails_replied) AS emails_replied
    FROM EmailAnalytics
    GROUP BY group_number
    ORDER BY group_number;
END;
$$ LANGUAGE PLPGSQL;

-- Cron job to create a new row for each week
CREATE OR REPLACE FUNCTION create_weekly_email_analytics_row() RETURNS VOID AS $$
BEGIN
    SET search_path = emails;

    INSERT INTO EmailAnalytics (week_start_date)
    VALUES (DATE_TRUNC('week', NOW()))
    ON CONFLICT (week_start_date) DO NOTHING;
END;
$$ LANGUAGE PLPGSQL;

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
        te.email_id::uuid NOT IN (
            SELECT e.email_id::uuid FROM EmailTracking e
        ) 
    OR 
        te.email_id IS NULL;

END;
$$ LANGUAGE PLPGSQL;

CREATE OR REPLACE FUNCTION set_email_delivered() RETURNS VOID AS $$
BEGIN
    SET search_path = emails;

    UPDATE EmailTracking e
    SET email_current_status = 'DELIVERED'
    WHERE email_current_status = 'SENT' AND NOW() - date_sent >= INTERVAL '5 hours';

    UPDATE EmailTracking e
    SET email_current_status = 'FAILED'
    WHERE email_current_status = 'RECEIVED' AND NOW() - date_sent >= INTERVAL '5 hours';

    -- Update analytics 
    -- ADd event

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

-- Schedule the weekly cron job
SELECT cron.schedule(
    'create_weekly_email_analytics_row',
    '0 0 * * 0', -- Every Sunday at midnight
    'SELECT emails.create_weekly_email_analytics_row();'
);

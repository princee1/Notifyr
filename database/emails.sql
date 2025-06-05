-- Active: 1740679093248@@localhost@5432@notifyr@emails
SET search_path = emails;

CREATE DOMAIN ESPProvider AS VARCHAR(25) CHECK (
    VALUE IN (
        'Google',
        'Microsoft',
        'Yahoo',
        'Apple',
        'ProtonMail',
        'Zoho',
        'AOL',
        'Untracked Provider'
    )
);

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
    esp_provider VARCHAR(25) DEFAULT 'Untracked Provider',
    contact_id UUID DEFAULT NULL,
    date_sent TIMESTAMPTZ DEFAULT NOW(),
    last_update TIMESTAMPTZ DEFAULT NOW(),
    expired_tracking_date TIMESTAMPTZ,
    email_current_status EmailStatus,
    subject VARCHAR(150),
    spam_label VARCHAR(50),
    spam_detection_confidence FLOAT,
    PRIMARY KEY (email_id),
    FOREIGN KEY (contact_id) REFERENCES contacts.Contact (contact_id) ON UPDATE CASCADE ON DELETE NO ACTION
);

CREATE TABLE IF NOT EXISTS TrackingEvent (
    event_id UUID DEFAULT uuid_generate_v1mc (),
    email_id UUID NOT NULL,
    current_event EmailStatus NOT NULL,
    description VARCHAR(200) DEFAULT NULL,
    date_event_received TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (event_id),
    FOREIGN KEY (email_id) REFERENCES EmailTracking (email_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS TrackedLinks (
    -- Define columns here as needed
);

-- Update EmailAnalytics table to track daily analytics
CREATE TABLE IF NOT EXISTS EmailAnalytics (
    analytics_id UUID DEFAULT uuid_generate_v1mc (),
    esp_provider VARCHAR(25) NOT NULL, -- Added esp_provider column
    day_start_date DATE NOT NULL DEFAULT DATE_TRUNC('day', NOW()), -- Changed to daily tracking
    emails_sent INT DEFAULT 0,
    emails_delivered INT DEFAULT 0,
    emails_opened INT DEFAULT 0,
    emails_bounced INT DEFAULT 0,
    emails_complaint INT DEFAULT 0,
    emails_replied INT DEFAULT 0,
    emails_failed INT DEFAULT 0,
    PRIMARY KEY (analytics_id),
    UNIQUE (day_start_date, esp_provider) -- Updated unique constraint for daily tracking
);

-- Function to upsert the latest EmailAnalytics row
-- Function to upsert Email Analytics with emails_complaint and emails_failed
CREATE OR REPLACE FUNCTION upsert_email_analytics(
    esp VARCHAR(25),
    sent_count INT,
    delivered_count INT,
    opened_count INT,
    bounced_count INT,
    complaint_count INT, -- Added emails_complaint parameter
    replied_count INT,
    failed_count INT -- Added emails_failed parameter
) RETURNS VOID AS $$
BEGIN
    SET search_path = emails;

    INSERT INTO EmailAnalytics (day_start_date, esp_provider, emails_sent, emails_delivered, emails_opened, emails_bounced, emails_complaint, emails_replied, emails_failed)
    VALUES (DATE_TRUNC('DAY', NOW()), esp, sent_count, delivered_count, opened_count, bounced_count, complaint_count, replied_count, failed_count)
    ON CONFLICT (day_start_date, esp_provider)
    DO UPDATE SET
        emails_sent = EmailAnalytics.emails_sent + EXCLUDED.emails_sent,
        emails_delivered = EmailAnalytics.emails_delivered + EXCLUDED.emails_delivered,
        emails_opened = EmailAnalytics.emails_opened + EXCLUDED.emails_opened,
        emails_bounced = EmailAnalytics.emails_bounced + EXCLUDED.emails_bounced,
        emails_complaint = EmailAnalytics.emails_complaint + EXCLUDED.emails_complaint, -- Updated emails_complaint
        emails_replied = EmailAnalytics.emails_replied + EXCLUDED.emails_replied,
        emails_failed = EmailAnalytics.emails_failed + EXCLUDED.emails_failed; -- Updated emails_failed
END;
$$ LANGUAGE PLPGSQL;

-- Function to aggregate email analytics dynamically based on grouping
CREATE OR REPLACE FUNCTION calculate_email_analytics_grouped(
    group_by_factor INT
) RETURNS TABLE (
    group_number INT,
    esp_provider VARCHAR(25),
    emails_sent INT,
    emails_delivered INT,
    emails_opened INT,
    emails_bounced INT,
    emails_complaint INT, -- Added emails_complaint to output
    emails_replied INT,
    emails_failed INT -- Added emails_failed to output
) AS $$
BEGIN
    RETURN QUERY
    SET search_path = emails;

    SELECT
        FLOOR(EXTRACT(EPOCH FROM (day_start_date - MIN(day_start_date) OVER ())) / (group_by_factor * 24 * 60 * 60)) + 1 AS group_number,
        esp_provider,
        SUM(emails_sent) AS emails_sent,
        SUM(emails_delivered) AS emails_delivered,
        SUM(emails_opened) AS emails_opened,
        SUM(emails_bounced) AS emails_bounced,
        SUM(emails_complaint) AS emails_complaint, -- Updated emails_complaint
        SUM(emails_replied) AS emails_replied,
        SUM(emails_failed) AS emails_failed -- Updated emails_failed
    FROM EmailAnalytics
    GROUP BY group_number, esp_provider
    ORDER BY group_number, esp_provider;
END;
$$ LANGUAGE PLPGSQL;

-- Cron job to create a new row for each day
CREATE OR REPLACE FUNCTION create_daily_email_analytics_row()
RETURNS VOID AS $$
DECLARE
    esp TEXT;
    esp_list TEXT[] := ARRAY[
        'Google',
        'Microsoft',
        'Yahoo',
        'Apple',
        'ProtonMail',
        'Zoho',
        'AOL',
        'Untracked Provider'
    ];
BEGIN
    SET search_path = emails;

    FOREACH esp IN ARRAY esp_list LOOP
        INSERT INTO EmailAnalytics (day_start_date, esp_provider)
        VALUES (DEFAULT, esp)
        ON CONFLICT (day_start_date, esp_provider) DO NOTHING;
    END LOOP;
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
DECLARE
    esp TEXT;
    sent_email_ids UUID[];
    received_email_ids UUID[];
BEGIN
    SET search_path = emails;

    -- Loop through each ESP provider
    FOR esp IN SELECT DISTINCT esp_provider FROM EmailTracking WHERE esp_provider IS NOT NULL LOOP
        -- Get sent email IDs for the current ESP provider
        sent_email_ids := ARRAY(
            SELECT email_id
            FROM EmailTracking
            WHERE email_current_status = 'SENT'
              AND esp_provider = esp
              AND NOW() - date_sent >= INTERVAL '1 hours'
        );

        -- Get received email IDs for the current ESP provider
        received_email_ids := ARRAY(
            SELECT email_id
            FROM EmailTracking
            WHERE email_current_status = 'RECEIVED'
              AND esp_provider = esp
              AND NOW() - date_sent >= INTERVAL '1 hours'
        );

        -- Update EmailTracking statuses for the current ESP provider
        UPDATE EmailTracking
        SET email_current_status = 'DELIVERED'
        WHERE email_id = ANY(sent_email_ids);

        UPDATE EmailTracking
        SET email_current_status = 'FAILED'
        WHERE email_id = ANY(received_email_ids);

        -- Upsert analytics for the current ESP provider
        PERFORM upsert_email_analytics(
            esp,
            0, -- emails_sent
            COALESCE(array_length(sent_email_ids, 1), 0), -- emails_delivered
            0,                                           -- emails_opened
            0, -- emails_bounced
            0,                                           -- emails_complaint
            0,                                           -- emails_replied
            COALESCE(array_length(received_email_ids, 1), 0)  -- emails_failed
        );

        -- Add events for 'DELIVERED' for the current ESP provider
        INSERT INTO emails.TrackingEvent (email_id, current_event, description)
        SELECT email_id, 'DELIVERED', 'Email marked as delivered after 1 hours'
        FROM unnest(sent_email_ids) AS email_id;

        -- Add events for 'FAILED' for the current ESP provider
        INSERT INTO emails.TrackingEvent (email_id, current_event, description)
        SELECT email_id, 'FAILED', 'Email marked as failed after 1 hours'
        FROM unnest(received_email_ids) AS email_id;
    END LOOP;
END;
$$ LANGUAGE PLPGSQL;

-- Schedule the function to run every hour using pg_cron
SELECT cron.schedule (
        'set_email_delivered_every_hour', -- Job name
        '0 * * * *', -- Cron expression for every hour
        'SELECT emails.set_email_delivered();'
    );

SELECT cron.schedule (
        'delete_expired_email_tracking_every_day', '0 0 * * *', -- Cron expression for every day at midnight
        'SELECT emails.delete_expired_email_tracking();'
    );

SELECT cron.schedule (
        'delete_non_mapped_email_event_every_day', '0 */3 * * *', -- Cron expression for every 3 hours
        'SELECT emails.delete_non_mapped_email_event();'
    );

-- Schedule the daily cron job
SELECT cron.schedule (
        'create_daily_email_analytics_row', '0 0 * * *', -- Every day at midnight
        'SELECT emails.create_daily_email_analytics_row();'
    );
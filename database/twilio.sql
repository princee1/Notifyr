-- Active: 1740679093248@@localhost@5432@notifyr@twilio
SET search_path = twilio;

-- Create domain for SMS Status
CREATE DOMAIN SMSStatus AS VARCHAR(50) CHECK (
    VALUE IN (
        'QUEUED',
        'SENT',
        'DELIVERED',
        'FAILED',
        'REPLIED',
        'RECEIVED',
        'BOUNCE',
        'REJECTED'
    )
);

CREATE DOMAIN Direction AS VARCHAR(1) CHECK (
    VALUE IN (
        'I', -- INBOUND
        'O' -- OUTBOUND
    )
);

-- Create domain for Call Status
CREATE DOMAIN CallStatus AS VARCHAR(50) CHECK (
    VALUE IN (
        'RECEIVED',
        'INITIATED',
        'COMPLETED',
        'NO-ANSWER',
        'DECLINED',
        'BOUNCE',
        'IN-PROGRESS',
        'RINGING',
        'FAILED',
        'SENT',
        'REJECTED'
    )
);

-- Update table for SMS Tracking
CREATE TABLE IF NOT EXISTS SMSTracking (
    sms_id UUID DEFAULT uuid_generate_v1mc (),
    sms_sid VARCHAR(60) UNIQUE DEFAULT NULL,
    contact_id UUID DEFAULT NULL,
    recipient VARCHAR(100) NOT NULL,
    sender VARCHAR(100) NOT NULL,
    date_sent TIMESTAMPTZ DEFAULT NOW(),
    last_update TIMESTAMPTZ DEFAULT NOW(),
    expired_tracking_date TIMESTAMPTZ,
    sms_current_status SMSStatus,
    price FLOAT DEFAULT NULL,
    price_unit VARCHAR(10) DEFAULT NULL,
    PRIMARY KEY (sms_id),
    FOREIGN KEY (contact_id) REFERENCES contacts.Contact (contact_id) ON UPDATE CASCADE ON DELETE SET NULL
);

-- Update table for Call Tracking
CREATE TABLE IF NOT EXISTS CallTracking (
    call_id UUID DEFAULT uuid_generate_v1mc (),
    call_sid VARCHAR(60) UNIQUE DEFAULT NULL,
    contact_id UUID DEFAULT NULL,
    recipient VARCHAR(100) NOT NULL,
    sender VARCHAR(100) NOT NULL,
    date_started TIMESTAMPTZ DEFAULT NOW(),
    last_update TIMESTAMPTZ DEFAULT NOW(),
    expired_tracking_date TIMESTAMPTZ,
    call_current_status CallStatus,
    duration INT DEFAULT 0,
    total_duration INT DEFAULT 0,
    price FLOAT DEFAULT NULL,
    price_unit VARCHAR(10) DEFAULT NULL,
    PRIMARY KEY (call_id),
    FOREIGN KEY (contact_id) REFERENCES contacts.Contact (contact_id) ON UPDATE CASCADE ON DELETE SET NULL
);

-- Update table for SMS Events
CREATE TABLE IF NOT EXISTS SMSEvent (
    event_id UUID DEFAULT uuid_generate_v1mc (),
    sms_id UUID DEFAULT NULL,
    sms_sid VARCHAR(60) DEFAULT NULL,
    direction Direction,
    current_event SMSStatus NOT NULL,
    description VARCHAR(200) DEFAULT NULL,
    date_event_received TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (event_id),
    FOREIGN KEY (sms_id) REFERENCES SMSTracking (sms_id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Update table for Call Events to include location details
CREATE TABLE IF NOT EXISTS CallEvent (
    event_id UUID DEFAULT uuid_generate_v1mc (),
    call_id UUID DEFAULT NULL,
    call_sid VARCHAR(60) DEFAULT NULL,
    direction Direction,
    current_event CallStatus NOT NULL,
    description VARCHAR(200) DEFAULT NULL,
    country VARCHAR(100) DEFAULT NULL, -- Added country column
    state VARCHAR(100) DEFAULT NULL, -- Added state column
    city VARCHAR(100) DEFAULT NULL, -- Added city column
    date_event_received TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (event_id),
    FOREIGN KEY (call_id) REFERENCES CallTracking (call_id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Create table for SMS Analytics
CREATE TABLE IF NOT EXISTS SMSAnalytics (
    analytics_id UUID DEFAULT uuid_generate_v1mc (),
    week_start_date DATE NOT NULL DEFAULT DATE_TRUNC('week', NOW()),
    direction Direction NOT NULL,
    sms_received INT DEFAULT 0,
    sms_sent INT DEFAULT 0,
    sms_rejected INT DEFAULT 0,
    sms_delivered INT DEFAULT 0,
    sms_failed INT DEFAULT 0,
    sms_bounce INT DEFAULT 0,
    total_price FLOAT DEFAULT 0, -- Added total price column
    -- average_price FLOAT DEFAULT 0, -- Added average price column
    PRIMARY KEY (analytics_id),
    UNIQUE (week_start_date, direction)
);

-- Update table for Call Analytics to include location details
CREATE TABLE IF NOT EXISTS CallAnalytics (
    analytics_id UUID DEFAULT uuid_generate_v1mc (),
    week_start_date DATE NOT NULL DEFAULT DATE_TRUNC('week', NOW()),
    direction Direction NOT NULL,
    country VARCHAR(100) DEFAULT NULL, -- Added country column
    state VARCHAR(100) DEFAULT NULL, -- Added state column
    city VARCHAR(100) DEFAULT NULL, -- Added city column
    calls_received INT DEFAULT 0,
    calls_sent INT DEFAULT 0,
    calls_rejected INT DEFAULT 0,
    calls_started INT DEFAULT 0,
    calls_completed INT DEFAULT 0,
    calls_failed INT DEFAULT 0,
    calls_bounce INT DEFAULT 0,
    calls_not_answered INT DEFAULT 0,
    calls_declined INT DEFAULT 0,
    total_price FLOAT DEFAULT 0, -- Added total price column
    -- average_price FLOAT DEFAULT 0, -- Added average price column
    total_duration INT DEFAULT 0, -- Added total duration column
    -- average_duration FLOAT DEFAULT 0, -- Added average duration column
    total_call_duration INT DEFAULT 0, -- Added total call duration column
    -- average_call_duration FLOAT DEFAULT 0, -- Added average call duration column
    PRIMARY KEY (analytics_id),
    UNIQUE (
        week_start_date,
        direction,
        country,
        state,
        city
    ) -- Updated unique constraint for location
);

CREATE OR REPLACE FUNCTION calculate_sms_analytics_grouped(
    group_by_factor INT -- Grouping factor in weeks
) RETURNS TABLE (
    group_number INT,
    direction Direction,
    sms_received INT,
    sms_sent INT,
    sms_rejected INT,
    sms_delivered INT,
    sms_failed INT,
    sms_bounce INT,
    total_price FLOAT

    -- average_price FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SET search_path = twilio;

    SELECT
        FLOOR(EXTRACT(EPOCH FROM (week_start_date - MIN(week_start_date) OVER ())) / (group_by_factor * 24 * 60 * 60)) + 1 AS group_number,
        direction,
        SUM(sms_received) AS sms_received,
        SUM(sms_sent) AS sms_sent,
        SUM(sms_rejected) AS sms_rejected,
        SUM(sms_delivered) AS sms_delivered,
        SUM(sms_failed) AS sms_failed,
        SUM(sms_bounce) AS sms_bounce,
        SUM(total_price) AS total_price
        -- AVG(average_price) AS average_price
    FROM SMSAnalytics
    GROUP BY group_number, direction
    ORDER BY group_number, direction;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION calculate_call_analytics_grouped(
    group_by_factor INT -- Grouping factor in days
) RETURNS TABLE (
    group_number INT,
    direction Direction,
    country VARCHAR(100),
    state VARCHAR(100),
    city VARCHAR(100),
    calls_received INT,
    calls_sent INT,
    calls_rejected INT,
    calls_started INT,
    calls_completed INT,
    calls_failed INT,
    calls_not_answered INT,
    calls_bounce INT,
    calls_declined INT,
    total_price FLOAT,
    average_price FLOAT,
    total_duration INT,
    -- average_duration FLOAT,
    total_call_duration INT -- Added total call duration column
    -- average_call_duration FLOAT -- Added average call duration column
) AS $$
BEGIN
    SET search_path = twilio;

    RETURN QUERY
    SELECT
        FLOOR(EXTRACT(EPOCH FROM (week_start_date - MIN(week_start_date) OVER ())) / (group_by_factor * 24 * 60 * 60)) + 1 AS group_number,
        direction,
        country,
        state,
        city,
        SUM(calls_received) AS calls_received,
        SUM(calls_sent) AS  calls_sent,
        SUM(calls_rejected) AS  calls_rejected,
        SUM(calls_started) AS calls_started,
        SUM(calls_completed) AS calls_completed,
        SUM(calls_failed) AS calls_failed,
        SUM(calls_not_answered) AS calls_not_answered,
        SUM(calls_bounce) AS calls_bounce,
        SUM(calls_declined) AS calls_declined,
        SUM(total_price) AS total_price,
        AVG(average_price) AS average_price,
        SUM(total_duration) AS total_duration,
        -- AVG(average_duration) AS average_duration,
        SUM(total_call_duration) AS total_call_duration
        -- AVG(average_call_duration) AS average_call_duration

    FROM CallAnalytics
    GROUP BY group_number, direction, country, state, city
    ORDER BY group_number, direction, country, state, city;
END;
$$ LANGUAGE plpgsql;

-- Function to upsert SMS Analytics with price data
CREATE OR REPLACE FUNCTION bulk_upsert_sms_analytics(
    d Direction, -- Added direction parameter
    received_count INT,
    sent_count INT,
    rejected_count INT,
    delivered_count INT,
    failed_count INT,
    bounced_count INT,
    total_price FLOAT
    -- average_price FLOAT
) RETURNS VOID AS $$
BEGIN
    SET search_path = twilio;

    INSERT INTO SMSAnalytics (week_start_date, direction,sms_received, sms_sent, sms_rejected,sms_delivered, sms_failed, sms_bounce, total_price)
    VALUES (DEFAULT, d,received_count, sent_count, rejected_count, delivered_count, failed_count, bounced_count, total_price)
    ON CONFLICT (week_start_date, direction) -- Updated conflict target for direction
    DO UPDATE SET
        sms_received = SMSAnalytics.sms_received + EXCLUDED.sms_received,
        sms_sent = SMSAnalytics.sms_sent + EXCLUDED.sms_sent,
        rejected_count = SMSAnalytics.rejected_count + EXCLUDED.rejected_count,
        sms_delivered = SMSAnalytics.sms_delivered + EXCLUDED.sms_delivered,
        sms_failed = SMSAnalytics.sms_failed + EXCLUDED.sms_failed,
        sms_bounce = SMSAnalytics.sms_bounce + EXCLUDED.sms_bounce,
        total_price = SMSAnalytics.total_price + EXCLUDED.total_price;
        -- average_price = (SMSAnalytics.total_price + EXCLUDED.total_price) / (SMSAnalytics.sms_sent + EXCLUDED.sms_sent);
END;
$$ LANGUAGE PLPGSQL;

CREATE TYPE call_analytics_input AS (
    direction Direction,
    country VARCHAR(100),
    state VARCHAR(100),
    city VARCHAR(100),
    received_count INT,
    sent_count INT,
    rejected_count INT,
    started_count INT,
    completed_count INT,
    failed_count INT,
    not_answered_count INT,
    bounced_count INT,
    declined_count INT,
    total_price FLOAT,
    total_duration INT,
    total_call_duration INT
);

CREATE OR REPLACE FUNCTION bulk_upsert_call_analytics(data call_analytics_input[]) RETURNS VOID AS $$
DECLARE
    record call_analytics_input;
BEGIN
    SET search_path = twilio;

    FOREACH record IN ARRAY data
    LOOP
        INSERT INTO CallAnalytics (week_start_date, direction, country, state, city,calls_received,calls_sent,calls_rejected, calls_started, calls_completed, calls_failed, calls_not_answered, calls_bounce, calls_declined, total_price, total_duration, total_call_duration)
        VALUES (DEFAULT, record.direction, record.country, record.state, record.city, record.received_count, record.sent_count,record.rejected_count, record.started_count, record.completed_count, record.failed_count, record.not_answered_count, record.bounced_count, record.declined_count, record.total_price, record.total_duration, record.total_call_duration)
        ON CONFLICT (week_start_date, direction, country, state, city)
        DO UPDATE SET
            calls_received = CallAnalytics.calls_received + EXCLUDED.calls_received,
            calls_sent = CallAnalytics.calls_sent + EXCLUDED.calls_sent,
            calls_rejected = CallAnalytics.calls_rejected + EXCLUDED.calls_rejected,
            calls_started = CallAnalytics.calls_started + EXCLUDED.calls_started,
            calls_completed = CallAnalytics.calls_completed + EXCLUDED.calls_completed,
            calls_failed = CallAnalytics.calls_failed + EXCLUDED.calls_failed,
            calls_not_answered = CallAnalytics.calls_not_answered + EXCLUDED.calls_not_answered,
            calls_bounce = CallAnalytics.calls_bounce + EXCLUDED.calls_bounce,
            calls_declined = CallAnalytics.calls_declined + EXCLUDED.calls_declined,
            total_price = CallAnalytics.total_price + EXCLUDED.total_price,
            average_price = (CallAnalytics.total_price + EXCLUDED.total_price) / (CallAnalytics.calls_started + EXCLUDED.calls_started),
            total_duration = CallAnalytics.total_duration + EXCLUDED.total_duration,
            total_call_duration = CallAnalytics.total_call_duration + EXCLUDED.total_call_duration;
    END LOOP;
END;
$$ LANGUAGE PLPGSQL;

-- Function to delete expired Tracking
CREATE OR REPLACE FUNCTION delete_expired_tracking() RETURNS VOID AS $$
BEGIN
    SET search_path = twilio;

    -- Delete expired SMS Tracking
    DELETE FROM SMSTracking
    WHERE expired_tracking_date <= NOW();

    -- Delete expired Call Tracking
    DELETE FROM CallTracking
    WHERE expired_tracking_date <= NOW();
END;
$$ LANGUAGE PLPGSQL;

-- Function to set SMS Delivered
CREATE OR REPLACE FUNCTION set_sms_delivered() RETURNS VOID AS $$
DECLARE
    sent_sms_ids UUID[];
    received_sms_ids UUID[];
    queued_sms_ids UUID[];
BEGIN
    SET search_path = twilio;

    sent_sms_ids := ARRAY(
        SELECT sms_id
        FROM SMSTracking
        WHERE  sms_current_status = 'SENT' AND NOW() - date_sent >= INTERVAL '1 hours'
    );

    received_sms_ids := ARRAY(
        SELECT sms_id
        FROM SMSTracking
        WHERE sms_current_status = 'RECEIVED' AND NOW() - date_sent >= INTERVAL '1 hours'
    );

    queued_sms_ids := ARRAY(
        SELECT sms_id
        FROM SMSTracking
        WHERE sms_current_status = 'QUEUED' AND NOW() - date_sent >= INTERVAL '1 hours'
    );

    UPDATE SMSTracking
    SET sms_current_status = 'DELIVERED'
    WHERE sms_id = ANY(queued_sms_ids);

    UPDATE SMSTracking
    SET sms_current_status = 'FAILED'
    WHERE sms_id = ANY(received_sms_ids);

    UPDATE SMSTracking
    SET sms_current_status = 'BOUNCE'
    WHERE sms_id = ANY(sent_sms_ids);

    PERFORM bulk_upsert_sms_analytics(
        'O',
        0,
        0,
        0,
        0, 
        COALESCE(array_length(queued_sms_ids, 1), 0),
        COALESCE(array_length(received_sms_ids, 1), 0),
        COALESCE(array_length(sent_sms_ids, 1), 0),
        0
        );

    INSERT INTO SMSEvent (sms_id, current_event, description)
    SELECT sms_id, 'DELIVERED', 'SMS marked as delivered after 1 hours'
    FROM unnest(queued_sms_ids) AS sms_id;

    INSERT INTO SMSEvent (sms_id, current_event, description)
    SELECT sms_id, 'FAILED', 'SMS marked as failed after 1 hours'
    FROM unnest(received_sms_ids) AS sms_id;

    INSERT INTO SMSEvent (sms_id, current_event, description)
    SELECT sms_id, 'BOUNCE', 'SMS marked as bounced after 1 hours'
    FROM unnest(sent_sms_ids) AS sms_id;
END;
$$ LANGUAGE PLPGSQL;

-- Function to set Call Completed
CREATE OR REPLACE FUNCTION set_call_completed() RETURNS VOID AS $$
DECLARE
    started_call_ids UUID[];
BEGIN
    SET search_path = twilio;

    -- started_call_ids := ARRAY(
    --     SELECT call_id
    --     FROM CallTracking
    --     WHERE call_current_status = 'RINGING' AND NOW() - date_started >= INTERVAL '1 hours'
    -- );

    -- UPDATE CallTracking
    -- SET call_current_status = 'NO-ANSWER'
    -- WHERE call_id = ANY(started_call_ids);

    -- PERFORM upsert_call_analytics(COALESCE(array_length(started_call_ids, 1), 0), COALESCE(array_length(started_call_ids, 1), 0), 0, 0, 0, 0, 0);

    -- INSERT INTO CallEvent (call_id, current_event, description)
    -- SELECT call_id, 'NO-ANSWER', 'Call marked as completed after 1 hours'
    -- FROM unnest(started_call_ids) AS call_id;
END;
$$ LANGUAGE PLPGSQL;

-- Function to create weekly SMS analytics row
CREATE OR REPLACE FUNCTION create_weekly_sms_analytics_row()
RETURNS VOID AS $$
DECLARE
    direction TEXT;
    direction_list TEXT[] := ARRAY['I', 'O'];
    week_start_date DATE := DATE_TRUNC('week', CURRENT_DATE);
BEGIN
    SET search_path = twilio;

    FOREACH direction IN ARRAY direction_list LOOP
        INSERT INTO SMSAnalytics (week_start_date, direction)
        VALUES (week_start_date, direction)
        ON CONFLICT (week_start_date, direction) DO NOTHING;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Schedule the weekly cron job
SELECT cron.schedule (
        'create_weekly_sms_analytics_row', '0 0 * * 0', -- Every Sunday at midnight
        'SELECT twilio.create_weekly_sms_analytics_row();'
    );

-- Schedule the functions using pg_cron
SELECT cron.schedule (
        'set_sms_delivered_every_hour', '0 * * * *', 'SELECT twilio.set_sms_delivered();'
    );

SELECT cron.schedule (
        'set_call_completed_every_hour', '0 * * * *', 'SELECT twilio.set_call_completed();'
    );

SELECT cron.schedule (
        'delete_expired_tracking_every_day', '0 0 * * *', 'SELECT twilio.delete_expired_tracking();'
    );

CREATE OR REPLACE VIEW FetchCallAnalyticsByWeek AS
SELECT
    analytics_id,
    week_start_date,
    direction,
    country,
    state,
    city,
    calls_received,
    calls_sent,
    calls_rejected,
    calls_started,
    calls_completed,
    calls_failed,
    calls_not_answered,
    calls_bounce, -- Added calls_bounce column
    total_price,
    total_duration,
    total_call_duration, -- Added total call duration
    (
        total_call_duration - total_duration
    ) AS ringing_duration -- Added ringing duration column
FROM CallAnalytics
ORDER BY week_start_date ASC;
-- Sort by oldest to newest week
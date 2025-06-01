SET search_path = twilio;

-- Create domain for SMS Status
CREATE DOMAIN SMSStatus AS VARCHAR(50) CHECK (
    VALUE IN (
        'QUEUED',
        'SENT',
        'DELIVERED',
        'FAILED',
        'RECEIVED'
    )
);

CREATE DOMAIN Direction AS VARCHAR(1) CHECK (
    VALUE IN (
        'I',-- INBOUND
        'O' -- OUTBOUND
    )
)

-- Create domain for Call Status
CREATE DOMAIN CallStatus AS VARCHAR(50) CHECK (
    VALUE IN (
        'RECEIVED'
        'COMPLETED',
        'NO-ANSWER',
        'RINGING',
        'ANSWERED'
    )
);

-- Update table for SMS Tracking
CREATE TABLE IF NOT EXISTS SMSTracking (
    sms_id UUID DEFAULT uuid_generate_v1mc (),
    message_sid VARCHAR(150) UNIQUE NOT NULL,
    recipient VARCHAR(100) NOT NULL,
    sender VARCHAR(100) NOT NULL,
    date_sent TIMESTAMPTZ DEFAULT NOW(),
    last_update TIMESTAMPTZ DEFAULT NOW(),
    expired_tracking_date TIMESTAMPTZ,
    sms_current_status SMSStatus,
    price FLOAT DEFAULT NULL,
    price_unit VARCHAR(10) DEFAULT NULL,
    PRIMARY KEY (sms_id)
);

-- Update table for Call Tracking
CREATE TABLE IF NOT EXISTS CallTracking (
    call_id UUID DEFAULT uuid_generate_v1mc (),
    call_sid VARCHAR(150) UNIQUE NOT NULL,
    recipient VARCHAR(100) NOT NULL,
    sender VARCHAR(100) NOT NULL,
    date_started TIMESTAMPTZ DEFAULT NOW(),
    last_update TIMESTAMPTZ DEFAULT NOW(),
    expired_tracking_date TIMESTAMPTZ,
    call_current_status CallStatus,
    duration INT DEFAULT NULL,
    price FLOAT DEFAULT NULL,
    price_unit VARCHAR(10) DEFAULT NULL,
    PRIMARY KEY (call_id)
);

-- Update table for SMS Events
CREATE TABLE IF NOT EXISTS SMSEvent (
    event_id UUID DEFAULT uuid_generate_v1mc (),
    sms_id UUID DEFAULT NULL,
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
    direction Direction,
    current_event CallStatus NOT NULL,
    description VARCHAR(200) DEFAULT NULL,
    country VARCHAR(100) DEFAULT NULL, -- Added country column
    state VARCHAR(100) DEFAULT NULL,   -- Added state column
    city VARCHAR(100) DEFAULT NULL,    -- Added city column
    date_event_received TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (event_id),
    FOREIGN KEY (call_id) REFERENCES CallTracking (call_id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Create table for SMS Analytics
CREATE TABLE IF NOT EXISTS SMSAnalytics (
    analytics_id UUID DEFAULT uuid_generate_v1mc (),
    week_start_date DATE NOT NULL DEFAULT DATE_TRUNC('week', NOW()),
    direction Direction NOT NULL,
    sms_sent INT DEFAULT 0,
    sms_delivered INT DEFAULT 0,
    sms_failed INT DEFAULT 0,
    total_price FLOAT DEFAULT 0, -- Added total price column
    average_price FLOAT DEFAULT 0, -- Added average price column
    PRIMARY KEY (analytics_id),
    UNIQUE (week_start_date,direction)
);

-- Update table for Call Analytics to include location details
CREATE TABLE IF NOT EXISTS CallAnalytics (
    analytics_id UUID DEFAULT uuid_generate_v1mc (),
    week_start_date DATE NOT NULL DEFAULT DATE_TRUNC('week', NOW()),
    direction Direction NOT NULL,
    country VARCHAR(100) DEFAULT NULL, -- Added country column
    state VARCHAR(100) DEFAULT NULL,   -- Added state column
    city VARCHAR(100) DEFAULT NULL,    -- Added city column
    calls_started INT DEFAULT 0,
    calls_completed INT DEFAULT 0,
    calls_failed INT DEFAULT 0,
    total_price FLOAT DEFAULT 0,       -- Added total price column
    average_price FLOAT DEFAULT 0,     -- Added average price column
    total_duration INT DEFAULT 0,      -- Added total duration column
    average_duration FLOAT DEFAULT 0,  -- Added average duration column
    PRIMARY KEY (analytics_id),
    UNIQUE (week_start_date, direction,country, state, city) -- Updated unique constraint for location
);


CREATE OR REPLACE FUNCTION calculate_call_analytics_grouped(
    group_by_factor INT -- Grouping factor in days
) RETURNS TABLE (
    group_number INT,
    direction VARCHAR(1),
    country VARCHAR(100),
    state VARCHAR(100),
    city VARCHAR(100),
    calls_started INT,
    calls_completed INT,
    calls_failed INT,
    total_price FLOAT,
    average_price FLOAT,
    total_duration INT,
    average_duration FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        FLOOR(EXTRACT(EPOCH FROM (week_start_date - MIN(week_start_date) OVER ())) / (group_by_factor * 24 * 60 * 60)) + 1 AS group_number,
        direction,
        country,
        state,
        city,
        SUM(calls_started) AS calls_started,
        SUM(calls_completed) AS calls_completed,
        SUM(calls_failed) AS calls_failed,
        SUM(total_price) AS total_price,
        AVG(average_price) AS average_price,
        SUM(total_duration) AS total_duration,
        AVG(average_duration) AS average_duration
    FROM CallAnalytics
    GROUP BY group_number, direction, country, state, city
    ORDER BY group_number, direction, country, state, city;
END;
$$ LANGUAGE plpgsql;

-- Function to upsert SMS Analytics with price data
CREATE OR REPLACE FUNCTION upsert_sms_analytics(
    sent_count INT,
    delivered_count INT,
    failed_count INT,
    total_price FLOAT,
    average_price FLOAT
) RETURNS VOID AS $$
BEGIN
    SET search_path = twilio;

    INSERT INTO SMSAnalytics (week_start_date, sms_sent, sms_delivered, sms_failed, total_price, average_price)
    VALUES (DEFAULT, sent_count, delivered_count, failed_count, total_price, average_price)
    ON CONFLICT (week_start_date)
    DO UPDATE SET
        sms_sent = SMSAnalytics.sms_sent + EXCLUDED.sms_sent,
        sms_delivered = SMSAnalytics.sms_delivered + EXCLUDED.sms_delivered,
        sms_failed = SMSAnalytics.sms_failed + EXCLUDED.sms_failed,
        total_price = SMSAnalytics.total_price + EXCLUDED.total_price,
        average_price = (SMSAnalytics.total_price + EXCLUDED.total_price) / (SMSAnalytics.sms_sent + EXCLUDED.sms_sent);
END;
$$ LANGUAGE PLPGSQL;

-- Function to upsert Call Analytics with location details
CREATE OR REPLACE FUNCTION upsert_call_analytics(
    direction VARCHAR(10),
    country VARCHAR(100),
    state VARCHAR(100),
    city VARCHAR(100),
    started_count INT,
    completed_count INT,
    failed_count INT,
    total_price FLOAT,
    average_price FLOAT,
    total_duration INT,
    average_duration FLOAT
) RETURNS VOID AS $$
BEGIN
    SET search_path = twilio;

    INSERT INTO CallAnalytics (week_start_date, direction, country, state, city, calls_started, calls_completed, calls_failed, total_price, average_price, total_duration, average_duration)
    VALUES (DEFAULT, direction, country, state, city, started_count, completed_count, failed_count, total_price, average_price, total_duration, average_duration)
    ON CONFLICT (week_start_date, direction, country, state, city) -- Updated conflict target for location
    DO UPDATE SET
        calls_started = CallAnalytics.calls_started + EXCLUDED.calls_started,
        calls_completed = CallAnalytics.calls_completed + EXCLUDED.calls_completed,
        calls_failed = CallAnalytics.calls_failed + EXCLUDED.calls_failed,
        total_price = CallAnalytics.total_price + EXCLUDED.total_price,
        average_price = (CallAnalytics.total_price + EXCLUDED.total_price) / (CallAnalytics.calls_started + EXCLUDED.calls_started),
        total_duration = CallAnalytics.total_duration + EXCLUDED.total_duration,
        average_duration = (CallAnalytics.total_duration + EXCLUDED.total_duration) / (CallAnalytics.calls_completed + EXCLUDED.calls_completed);
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
BEGIN
    SET search_path = twilio;

    sent_sms_ids := ARRAY(
        SELECT sms_id
        FROM SMSTracking
        WHERE sms_current_status = 'SENT' AND NOW() - date_sent >= INTERVAL '1 hours'
    );

    UPDATE SMSTracking
    SET sms_current_status = 'DELIVERED'
    WHERE sms_id = ANY(sent_sms_ids);

    PERFORM upsert_sms_analytics(COALESCE(array_length(sent_sms_ids, 1), 0), COALESCE(array_length(sent_sms_ids, 1), 0), 0, 0, 0);

    INSERT INTO SMSEvent (sms_id, current_event, description)
    SELECT sms_id, 'DELIVERED', 'SMS marked as delivered after 1 hours'
    FROM unnest(sent_sms_ids) AS sms_id;
END;
$$ LANGUAGE PLPGSQL;

-- Function to set Call Completed
CREATE OR REPLACE FUNCTION set_call_completed() RETURNS VOID AS $$
DECLARE
    started_call_ids UUID[];
BEGIN
    SET search_path = twilio;

    started_call_ids := ARRAY(
        SELECT call_id
        FROM CallTracking
        WHERE call_current_status = 'ANSWERED' AND NOW() - date_started >= INTERVAL '1 hours'
    );

    UPDATE CallTracking
    SET call_current_status = 'COMPLETED'
    WHERE call_id = ANY(started_call_ids);

    PERFORM upsert_call_analytics(COALESCE(array_length(started_call_ids, 1), 0), COALESCE(array_length(started_call_ids, 1), 0), 0, 0, 0, 0, 0);

    INSERT INTO CallEvent (call_id, current_event, description)
    SELECT call_id, 'COMPLETED', 'Call marked as completed after 1 hours'
    FROM unnest(started_call_ids) AS call_id;
END;
$$ LANGUAGE PLPGSQL;

CREATE OR REPLACE FUNCTION create_weekly_call_analytics_row()
RETURNS VOID AS $$
DECLARE
    direction_list TEXT[] := ARRAY['I', 'O']; -- Inbound and Outbound directions
    direction TEXT;
    week_start_date DATE := DATE_TRUNC('week', CURRENT_DATE); -- Start of the current week
BEGIN
    SET search_path = twilio;

    FOREACH direction IN ARRAY direction_list LOOP
        INSERT INTO CallAnalytics (week_start_date, direction)
        VALUES (week_start_date, direction)
        ON CONFLICT (week_start_date, direction) DO NOTHING;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Schedule the weekly row creation function using pg_cron
SELECT cron.schedule(
    'create_weekly_call_analytics_row', '0 0 * * 0', -- Every Sunday at midnight
    'SELECT twilio.create_weekly_call_analytics_row();'
);
-- Schedule the functions using pg_cron
SELECT cron.schedule (
        'set_sms_delivered_every_hour', '0 * * * *',
        'SELECT twilio.set_sms_delivered();'
    );

SELECT cron.schedule (
        'set_call_completed_every_hour', '0 * * * *',
        'SELECT twilio.set_call_completed();'
    );

SELECT cron.schedule (
        'delete_expired_tracking_every_day', '0 0 * * *',
        'SELECT twilio.delete_expired_tracking();'
    );

    CREATE OR REPLACE VIEW FetchCallAnalyticsByWeek AS
    SELECT
        analytics_id,
        week_start_date,
        direction,
        country,
        state,
        city,
        calls_started,
        calls_completed,
        calls_failed,
        total_price,
        average_price,
        total_duration,
        average_duration
    FROM CallAnalytics
    ORDER BY week_start_date ASC; -- Sort by oldest to newest week
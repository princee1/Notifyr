SET search_path = campaigns;


CREATE TABLE Campaign (
    campaign_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    campaign_short_id VARCHAR(6), 
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE CampaignAnalytics (
    id SERIAL PRIMARY KEY,
    utm_source VARCHAR(50),
    utm_medium VARCHAR(50),
    utm_campaign VARCHAR(50),
    utm_term VARCHAR(50),
    utm_content TEXT,
    device public.DeviceType,
    timestamp TIMESTAMPTZ WITH TIME ZONE DEFAULT now()
);

CREATE TABLE AggreateCampaignAnalytics (
    id SERIAL PRIMARY KEY,
    campaign_id UUID REFERENCES Campaign(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    event_count INT DEFAULT 0,
    last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION delete_old_campaigns() RETURNS VOID AS $$
BEGIN
    DELETE FROM Campaign WHERE end_date < NOW() - INTERVAL '30 days';
    DELETE FROM CampaignAnalytics WHERE campaign_id NOT IN (SELECT id FROM Campaign);
END;
$$ LANGUAGE plpgsql;


SELECT cron.schedule('0 0 * * *', 'CALL delete_old_campaigns()');

CREATE OR REPLACE FUNCTION compute_campaign_limit() RETURNS TRIGGER AS $compute_campaign_limit$
DECLARE
    campaign_count INT;

BEGIN
    SELECT 
        COUNT(*) 
    INTO 
        campaign_count 
    FROM 
        Campaign;

    IF campaign_count >= 5 THEN
        RAISE EXCEPTION 'Campaign Limit Reached';
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$compute_campaign_limit$ LANGUAGE plpgsql;

CREATE TRIGGER limit_campaign
BEFORE INSERT ON Campaign
FOR EACH ROW
EXECUTE FUNCTION compute_campaign_limit();
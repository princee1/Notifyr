
SET search_path = emails;

CREATE DOMAIN EmailStatus AS VARCHAR(50) CHECK (VALUE IN (
    'SENT',
    'DELIVERED',
    'SOFT-BOUNCE',
    'HARD-BOUNCE'
    'MAILBOX-FULL',
    'OPENED',
    'LINK-CLICKED',
    'FAILED',
    'BLOCKED',
    'COMPLAINT',
    'DEFERRED',
    'DELAYED'
))


CREATE TABLE IF NOT EXISTS EmailTracking (
    email_id UUID  DEFAULT uuid_generate_v1mc ()
    mail_id VARCHAR(150) NOT NULL,
    recipient VARCHAR(100) NOT NULL,
    date_sent TIMESTAMPTZ DEFAULT NOW(),
    last_update TIMESTAMPTZ DEFAULT NOW(),
    expired_tracking_date TIMESTAMPTZ, 
    email_current_status EmailStatus,
    PRIMARY KEY (email_id)
    
)

CREATE TABLE IF NOT EXISTS TrackingEvent(
    event_id UUID  DEFAULT uuid_generate_v1mc ()
    email_id UUID NOT NULL,
    current_event EmailStatus NOT NULL,
    date_event_received TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (event_id),
    Foreign Key (email_id) REFERENCES EmailTracking (email_id) ON DELETE SET NULL ON UPDATE CASCADE

)

CREATE TABLE IF NOT EXISTS TrackedLinks(


)


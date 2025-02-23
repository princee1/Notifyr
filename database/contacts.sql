DROP SCHEMA IF  EXISTS contacts CASCADE;
CREATE SCHEMA contacts;
SET search_path TO contacts;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS Contact (
    PRIMARY KEY contact_id  UUID DEFAULT uuid_generate_v5(),
    first_name  VARCHAR(50) NOT NULL,
    last_name   VARCHAR(50) NOT NULL,
    email       VARCHAR(50) UNIQUE NOT NULL,
    phone       VARCHAR(50) UNIQUE,
    app_registered  BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
)

CREATE TABLE IF NOT EXISTS Security (
    PRIMARY KEY security_id UUID  DEFAULT uuid_generate_v4(),
    FOREIGN KEY contact_id UUID REFERENCES Contact(contact_id) ON DELETE CASCADE ON UPDATE CASCADE,
    security_code TEXT,
    security_phrase TEXT,
    voice_embedding FLOAT[],
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
)

-- CREATE TABLE IF NOT EXISTS Subscription (
--     subscription_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
--     contact_id      UNIQUE UUID REFERENCES Contact(contact_id),
--     email_status          SubscriptionStatus NOT NULL,
--     sms_status            SubscriptionStatus NOT NULL,
--     created_at      TIMESTAMP DEFAULT NOW(),
--     updated_at      TIMESTAMP DEFAULT NOW()
-- )
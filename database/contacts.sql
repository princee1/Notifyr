DROP SCHEMA IF  EXISTS contacts CASCADE;
CREATE SCHEMA contacts;
SET search_path TO contacts;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS Contact (
    contact_id  UUID PRIMARY KEY DEFAULT uuid_generate_v5(),
    first_name  VARCHAR(50) NOT NULL,
    last_name   VARCHAR(50) NOT NULL,
    email       VARCHAR(50) UNIQUE NOT NULL,
    phone       VARCHAR(50) UNIQUE,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
)

CREATE TABLE IF NOT EXISTS Security (
    security_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contact_id  UNIQUE UUID REFERENCES Contact(contact_id),
    security_code TEXT,
    security_phrase TEXT,
    embedding_vector FLOAT[],
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
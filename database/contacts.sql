-- Active: 1740679093248@@127.0.0.1@5432@notifyr@contacts
DROP SCHEMA IF  EXISTS contacts CASCADE;
CREATE SCHEMA contacts;
SET search_path = contacts;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE DOMAIN Lang AS VARCHAR(15) CHECK (VALUE IN ('fr','en'))

CREATE DOMAIN SubscriptionStatus AS VARCHAR(20) CHECK (VALUE IN ('Active','Inactive'))

CREATE TABLE IF NOT EXISTS Contact (
    contact_id  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name  VARCHAR(50) NOT NULL,
    last_name   VARCHAR(50) NOT NULL,
    email       VARCHAR(50) UNIQUE NOT NULL,
    phone       VARCHAR(50) UNIQUE,
    app_registered  BOOLEAN DEFAULT FALSE,
    lang    Lang,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
)

CREATE TABLE IF NOT EXISTS SecurityContact (
    security_id  UUID PRIMARY KEY  DEFAULT uuid_generate_v4(),
    contact_id  UUID,
    security_code TEXT,
    security_phrase TEXT,
    voice_embedding FLOAT[],
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (contact_id) REFERENCES Contact(contact_id) ON DELETE CASCADE ON UPDATE CASCADE
)

CREATE TABLE IF NOT EXISTS SubscriptionContact (
    subscription_id UUID DEFAULT uuid_generate_v4(),
    contact_id UUID UNIQUE,
    email_status SubscriptionStatus NOT NULL,
    sms_status SubscriptionStatus NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (subscription_id),
    FOREIGN KEY (contact_id) REFERENCES Contact(contact_id) ON DELETE CASCADE ON UPDATE CASCADE
)
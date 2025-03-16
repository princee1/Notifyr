-- Active: 1740679093248@@127.0.0.1@5432@notifyr@security
DROP SCHEMA IF EXISTS security CASCADE;

CREATE SCHEMA security;

SET search_path = security;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE EXTENSION IF NOT EXISTS pg_cron;

-- NOTE or create a schedule for each row using a Trigger

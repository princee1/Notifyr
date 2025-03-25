-- Active: 1740679093248@@127.0.0.1@5432@notifyr@cron
SET search_path = cron;

CREATE OR REPLACE FUNCTION cron.clear_job_details() RETURNS VOID AS $$
BEGIN
    SET search_path = cron;
    DELETE FROM cron.job_run_details;
END $$ LANGUAGE PLPGSQL;


SELECT cron.schedule(
    'clear job details', '0 0 * * 0', 'SELECT cron.clear_job_details();'
);

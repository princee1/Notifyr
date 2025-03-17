-- Active: 1740679093248@@127.0.0.1@5432@notifyr@security
DROP SCHEMA IF EXISTS security CASCADE;

CREATE SCHEMA security;

SET search_path = security;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";





-- NOTE or create a schedule for each row using a Trigger

-- -- Create the pgAgent job
-- INSERT INTO pgagent.pga_job (
--     jobid, jobname, jobdesc, jobhostagent, jobenabled
-- ) VALUES (
--     DEFAULT, 'Delete Expired SubsContent', 'Deletes expired SubsContent entries', '', true
-- );

-- -- Get the job ID of the newly created job
-- SELECT currval('pgagent.pga_job_jobid_seq');

-- -- Create a schedule for the job (run daily at midnight)
-- INSERT INTO pgagent.pga_schedule (
--     jscjobid, jscname, jscdesc, jscenabled, jscweekdays, jscmonthdays, jsctime
-- ) VALUES (
--     <job_id>, 'Daily at Midnight', 'Runs daily at midnight', true, '1111111', '1', '00:00'
-- );

-- -- Create a step for the job to call the function
-- INSERT INTO pgagent.pga_jobstep (
--     jstjobid, jstname, jstdesc, jstenabled, jstkind, jstcode, jstdbname
-- ) VALUES (
--     <job_id>, 'Call delete_expired_subscontent', 'Calls the delete_expired_subscontent function', true, 'sql', 'SELECT delete_expired_subscontent();', 'notifyr'
-- );

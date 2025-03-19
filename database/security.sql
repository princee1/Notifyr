-- Active: 1740679093248@@127.0.0.1@5432@notifyr@security
SET search_path = security;


CREATE OR REPLACE FUNCTION secure_random_string(length INT) RETURNS TEXT AS $$
DECLARE
    raw_bytes BYTEA;
    encoded TEXT;
    result TEXT;
BEGIN
    raw_bytes := gen_random_bytes(length);
    encoded := encode(raw_bytes, 'base64');
    RETURN substring(result FROM 1 FOR length);
END;
$$ LANGUAGE plpgsql;



CREATE DOMAIN Scope AS VARCHAR(25) CHECK (
    VALUE IN ('SoloDolo', 'Organization')
);


CREATE TABLE IF NOT EXISTS GroupClient (
    group_id UUID DEFAULT uuid_generate_v4(),
    group_name VARCHAR(80) UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (group_id)
);

CREATE TABLE  IF NOT EXISTS Client (
    client_id UUID DEFAULT uuid_generate_v4 (),
    client_name VARCHAR(120) UNIQUE,
    client_scope Scope DEFAULT 'SoloDolo',
    group_id UUID DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (client_id),
    FOREIGN KEY (group_id) REFERENCES GroupClient (group_id) ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE  IF NOT EXISTS Challenge (
    client_id UUID DEFAULT uuid_generate_v4(),
    challenge_auth TEXT UNIQUE NOT NULL DEFAULT secure_random_string(64),
    created_at_auth TIMESTAMPTZ DEFAULT NOW(),
    expired_at_auth TIMESTAMPTZ,
    challenge_refresh TEXT UNIQUE NOT NULL DEFAULT secure_random_string(64),
    created_at_refresh TIMESTAMPTZ DEFAULT NOW(),
    expired_at_refresh TIMESTAMPTZ,
    PRIMARY KEY (client_id),
    FOREIGN KEY (client_id) REFERENCES Client (client_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS Blacklist (
    blacklist_id UUID DEFAULT uuid_generate_v4(),
    client_id UUID DEFAULT NULL,
    group_id UUID DEFAULT NULL,
    create_at TIMESTAMPTZ DEFAULT NOW(),
    expired_at TiMESTAMPTZ,
    PRIMARY KEY (blacklist_id),
    FOREIGN KEY (group_id) REFERENCES GroupClient (group_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (client_id) REFERENCES Client (client_id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- add a trigger to delete expired blacklist entries
-- add a trigger to delete expired challenge entries
-- add a trigger to delete expired refresh entries



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
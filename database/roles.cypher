// ================================
// ROLE: notifyr-app (read/write + schema privileges)
// ================================

// Create role
CREATE ROLE notifyr-app;

// Grant access to database
GRANT ACCESS ON DATABASE notifyr TO notifyr-app;

// Graph-level privileges
GRANT MATCH, CREATE, DELETE, SET PROPERTY, REMOVE PROPERTY
  ON GRAPH notifyr TO notifyr-app;

// Schema privileges
GRANT CREATE INDEX ON DATABASE notifyr TO notifyr-app;
GRANT DROP INDEX ON DATABASE notifyr TO notifyr-app;
GRANT CREATE CONSTRAINT ON DATABASE notifyr TO notifyr-app;
GRANT DROP CONSTRAINT ON DATABASE notifyr TO notifyr-app;

// ================================
// ROLE: notifyr-admin (full privileges)
// ================================

// Create role
CREATE ROLE notifyr-admin;

// Grant full privileges on database
GRANT ALL PRIVILEGES ON DATABASE notifyr TO notifyr-admin;
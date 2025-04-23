#!/bin/bash

# Start original entrypoint in the background
docker-entrypoint.sh postgres &

# Wait for Postgres to be ready
until pg_isready -U "$POSTGRES_USER"; do
  echo "⏳ Waiting for Postgres..."
  sleep 1
done

echo "🚀 Postgres is ready, running custom command..."


echo "Setting up the Notifyr DB - Running custom setup.sh script..."

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/setup.sql

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/security.sql

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/contacts.sql

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/emails.sql

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/links.sql

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/cron.sql

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/data.sql


echo "setup.sh completed."

wait

#!/bin/bash
set -e

echo "📂 Initialize Notifyr Postgres Database"

NOTIFYR_DATABASE=notifyr
INIT_NOTIFYR_DB=${INIT_NOTIFYR_DB:-off}


echo "📂 Running admin setup operations..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/admin.sql
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/public.sql
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/security/setup.sql

echo "📂 Running logic schema..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/security/clients.sql

if [ "$INIT_NOTIFYR_DB" = "on" ]; then

    echo "📂 Creating notifyr admin user"
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE USER \"$NOTIFYR_POSTGRES_USER\" WITH PASSWORD '$NOTIFYR_POSTGRES_PASSWORD';"
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE DATABASE \"$NOTIFYR_DATABASE\" OWNER \"$NOTIFYR_POSTGRES_USER\";"
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "ALTER ROLE \"$NOTIFYR_POSTGRES_USER\" CREATEROLE;"

    echo "📂 Running admin setup operation in notifyr db..."
    psql -U "$POSTGRES_USER" -d "$NOTIFYR_DATABASE" -f /database/admin.sql
    psql -U "$POSTGRES_USER" -d "$NOTIFYR_DATABASE" -f /database/public.sql
    psql -U "$POSTGRES_USER" -d "$NOTIFYR_DATABASE" -f /database/notifyr/setup.sql

    echo "📂 Running logic schema in notifyr db..." 
    psql -U "$POSTGRES_USER" -d "$NOTIFYR_DATABASE" -f /database/notifyr/contacts.sql
    psql -U "$POSTGRES_USER" -d "$NOTIFYR_DATABASE" -f /database/notifyr/emails.sql
    psql -U "$POSTGRES_USER" -d "$NOTIFYR_DATABASE" -f /database/notifyr/links.sql
    # psql -U "$POSTGRES_USER" -d "$NOTIFYR_DATABASE" -f /database/notifyr/notifications.sql
    # psql -U "$POSTGRES_USER" -d "$NOTIFYR_DATABASE" -f /database/notifyr/campaigns.sql
    # psql -U "$POSTGRES_USER" -d "$NOTIFYR_DATABASE" -f /database/notifyr/mta.sql
    psql -U "$POSTGRES_USER" -d "$NOTIFYR_DATABASE" -f /database/notifyr/twilio.sql

    echo "📂 Running cron..."
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/notifyr/cron.sql


fi


echo "✅ setup.sh completed."

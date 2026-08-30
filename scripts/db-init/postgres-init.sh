#!/bin/bash
set -e

echo "📂 Initialize Notifyr Postgres Database"

NOTIFYR_DATABASE=notifyr
INIT_NOTIFYR_DB=${INIT_NOTIFYR_DB:-off}

if [ "$INIT_NOTIFYR_DB" != "on" ]; then

    echo "📂 Creating notifyr admin user"
    psql -U "$POSTGRES_USER" -c "CREATE USER $NOTIFYR_POSTGRES_USER WITH PASSWORD '$NOTIFYR_POSTGRES_PASSWORD';"
    psql -U "$POSTGRES_USER" -c "CREATE DATABASE $NOTIFYR_DATABASE OWNER $NOTIFYR_POSTGRES_USER;"
    
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

    echo "📂 Running cron for notifyr db"
    psql -U "$POSTGRES_USER" -d "$NOTIFYR_DB" -f /database/cron.sql
fi

echo "📂 Running admin setup operations..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/admin.sql
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/public.sql
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/security/setup.sql

echo "📂 Running logic schema..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/security/client.sql

echo "📂 Running cron for notifyr db"
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/cron.sql

echo "✅ setup.sh completed."

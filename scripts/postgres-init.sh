#!/bin/bash
echo "📂 Running setup.sql..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/setup.sql

echo "📂 Running admin.sql..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/admin.sql


echo "📂 Running security.sql..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/security.sql

echo "📂 Running contacts.sql..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/contacts.sql

echo "📂 Running emails.sql..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/emails.sql

echo "📂 Running links.sql..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/links.sql

echo "📂 Running cron.sql..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/cron.sql

# echo "📂 Running notifications.sql..."
# psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/notifications.sql

# echo "📂 Running campaigns.sql..."
# psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/campaigns.sql

# echo "📂 Running mta.sql..."
# psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/mta.sql

echo "📂 Running twilio.sql..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/twilio.sql

echo "📂 Running data.sql..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/data.sql

echo "✅ setup.sh completed."

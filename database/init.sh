!/bin/bash

echo "📦 Setting up the Notifyr DB - Running custom setup.sh script..."

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/setup.sql

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/security.sql

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/contacts.sql

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/emails.sql

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/links.sql

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/cron.sql

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/data.sql

echo "✅ setup.sh completed."


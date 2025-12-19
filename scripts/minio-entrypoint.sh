#!/usr/bin/env bash
set -e

unset MINIO_ROOT_USER
unset MINIO_ROOT_PASSWORD

# === Redis event configuration ===
export MINIO_NOTIFY_REDIS_ENABLE_NOTIFYR="${NOTIFY_REDIS_ENABLE:-on}"
export MINIO_NOTIFY_REDIS_ADDRESS_NOTIFYR="redis:6379"
export MINIO_NOTIFY_REDIS_KEY_NOTIFYR="${NOTIFY_REDIS_KEY:-s3_object_events}"
export MINIO_NOTIFY_REDIS_QUEUE_LIMIT_NOTIFYR="${NOTIFY_REDIS_QUEUE_LIMIT:-1000}"
export MINIO_NOTIFY_REDIS_FORMAT="namespace"
export MINIO_NOTIFY_REDIS_STREAM="on"

CONFIG_DIR=/run/secrets

minio server /data --config-dir $CONFIG_DIR --console-address ":9001" &
MINIO_PID=$!

sleep 9
echo "Minio is UP!"

VAULT_ACCESS_KEY=vaultadmin-minio
VAULT_SECRET_KEY=${MINIO_VAULT_PASSWORD}

accessKey=$(jq -r '.credential.accessKey' "$CONFIG_DIR/config.json")
secretKey=$(jq -r '.credential.secretKey' "$CONFIG_DIR/config.json")

create_bucket() {
    BUCKET="$1"
    QUOTA="$2"

    if ! mc stat "$BUCKET" >/dev/null 2>&1; then
        mc mb "$BUCKET"
        mc version enable "$BUCKET"
        mc quota set "$BUCKET" --size "$QUOTA"
    fi
}

mc alias set notifyr http://localhost:9000 "$accessKey" "$secretKey" >/dev/null

# ===============================
# Add vaultadmin-minio ONLY IF NOT EXISTS
# ===============================
echo "Checking if user '$VAULT_ACCESS_KEY' exists..."

if mc admin user info notifyr "$VAULT_ACCESS_KEY" >/dev/null 2>&1; then
    echo "User '$VAULT_ACCESS_KEY' already exists. Skipping creation."
else
    echo "User '$VAULT_ACCESS_KEY' does NOT exist. Creating..."
    mc admin user add notifyr "$VAULT_ACCESS_KEY" "$VAULT_SECRET_KEY"
    mc admin policy attach notifyr consoleAdmin --user "$VAULT_ACCESS_KEY"
    #mc admin policy attach notifyr vault-admin --user "$VAULT_ACCESS_KEY"
fi

create_bucket notifyr/static "$STATIC_STORAGE_LIMIT"
create_bucket notifyr/assets "$ASSETS_STORAGE_LIMIT"

if [ "$S3_MODE" = "dev" ]; then
    mc cp --recursive /app/objects/assets/ notifyr/assets/
    mc cp --recursive /app/objects/static/ notifyr/static/
fi

# ===============================
# Event creation (idempotent)
# ===============================
notifyr_event_status=$(mc event list notifyr/assets --json | jq -r '.status')

if [ "$notifyr_event_status" = "success" ]; then
    echo "Notifyr events already added"
else
    mc event add notifyr/assets arn:minio:sqs::NOTIFYR:redis --event put,delete
fi

mc alias remove notifyr >/dev/null
accessKey=""
secretKey=""

wait "$MINIO_PID"
